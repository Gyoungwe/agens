import asyncio
import time
from contextlib import suppress
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Callable, Dict, List, Optional


@dataclass
class HarnessStageSpec:
    name: str
    agent_id: str
    prompt: str
    timeout_seconds: int = 120
    critical: bool = False
    depends_on: List[str] = field(default_factory=list)
    knowledge_topic: Optional[str] = None
    qc_gate: bool = False


@dataclass
class HarnessStageResult:
    stage: str
    agent_id: str
    status: str
    elapsed_ms: int
    trace_id: str
    error: Optional[str]
    output: str
    provenance: Dict[str, Any] = field(default_factory=dict)
    needs_user_input: bool = False
    user_question: Optional[str] = None
    required_fields: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        base = {
            "stage": self.stage,
            "agent_id": self.agent_id,
            "status": self.status,
            "elapsed_ms": self.elapsed_ms,
            "trace_id": self.trace_id,
            "error": self.error,
            "output": self.output,
        }
        if self.provenance is not None:
            base["provenance"] = self.provenance
        if self.needs_user_input:
            base["needs_user_input"] = True
            base["user_question"] = self.user_question
            base["required_fields"] = self.required_fields
        return base


class HarnessStateManager:
    def __init__(self, session_manager, logger):
        self.session_manager = session_manager
        self.logger = logger

    def save_checkpoint(
        self,
        session_id: str,
        trace_id: str,
        stage_name: str,
        payload: Dict[str, Any],
    ) -> None:
        if not self.session_manager or not hasattr(self.session_manager, "store"):
            return

        checkpoint = {
            "type": "checkpoint",
            "stage": stage_name,
            "timestamp": datetime.now().isoformat(),
            "payload": payload,
        }
        self.session_manager.store.save_result(
            session_id=session_id,
            trace_id=trace_id,
            agent_id="harness_checkpoint",
            result=checkpoint,
            status="checkpoint",
        )

        # Durable read-back verification for immediate recovery confidence
        verified = False
        if hasattr(self.session_manager.store, "get_results_by_trace"):
            rows = self.session_manager.store.get_results_by_trace(trace_id)
            verified = any(r.get("agent_id") == "harness_checkpoint" for r in rows)
        else:
            rows = self.session_manager.store.get_results(session_id)
            verified = any(
                r.get("trace_id") == trace_id
                and r.get("agent_id") == "harness_checkpoint"
                for r in rows
            )

        if not verified:
            self.logger.warning(
                f"bio_harness_checkpoint_verify_failed session_id={session_id} trace_id={trace_id} stage={stage_name}"
            )

        self.logger.info(
            f"bio_harness_checkpoint_saved session_id={session_id} trace_id={trace_id} stage={stage_name}"
        )

    def save_stage_result(
        self,
        session_id: str,
        trace_id: str,
        result: HarnessStageResult,
    ) -> None:
        if not self.session_manager or not hasattr(self.session_manager, "store"):
            return

        self.session_manager.store.save_result(
            session_id=session_id,
            trace_id=trace_id,
            agent_id=result.agent_id,
            result=result.to_dict(),
            status=result.status,
        )

    def last_checkpoint(self, session_id: str) -> Dict[str, Any]:
        if not self.session_manager or not hasattr(self.session_manager, "store"):
            return {}

        rows = self.session_manager.store.get_results(session_id)
        for row in reversed(rows):
            if row.get("agent_id") == "harness_checkpoint" and row.get("result"):
                return row
        return {}


class ExecutionBoundary:
    def __init__(self, logger):
        self.logger = logger

    async def run_with_timeout(
        self,
        stage_name: str,
        timeout_seconds: int,
        awaitable,
        progress_callback=None,
    ):
        started = time.time()
        task = asyncio.create_task(awaitable)
        progress_task = None

        async def emit_progress_loop():
            if progress_callback is None:
                return
            while not task.done():
                await asyncio.sleep(2)
                if task.done():
                    break
                elapsed_ms = int((time.time() - started) * 1000)
                await progress_callback(elapsed_ms)

        if progress_callback is not None:
            progress_task = asyncio.create_task(emit_progress_loop())
        try:
            output = await asyncio.wait_for(task, timeout=timeout_seconds)
            elapsed_ms = int((time.time() - started) * 1000)
            return {
                "status": "ok" if output else "error",
                "output": output or "",
                "error": None if output else "empty output",
                "elapsed_ms": elapsed_ms,
            }
        except asyncio.TimeoutError:
            task.cancel()
            with suppress(asyncio.CancelledError):
                await task
            elapsed_ms = int((time.time() - started) * 1000)
            self.logger.warning(
                f"bio_harness_timeout stage={stage_name} timeout_seconds={timeout_seconds}"
            )
            return {
                "status": "timeout",
                "output": "",
                "error": f"stage exceeded timeout({timeout_seconds}s)",
                "elapsed_ms": elapsed_ms,
            }
        except Exception as e:
            if not task.done():
                task.cancel()
                with suppress(asyncio.CancelledError):
                    await task
            elapsed_ms = int((time.time() - started) * 1000)
            return {
                "status": "error",
                "output": "",
                "error": f"{type(e).__name__}: {e}",
                "elapsed_ms": elapsed_ms,
            }
        finally:
            if progress_task is not None:
                progress_task.cancel()
                with suppress(asyncio.CancelledError):
                    await progress_task


class BioWorkflowHarness:
    def __init__(
        self,
        session_manager,
        logger,
        event_emitter: Optional[Callable[..., Any]] = None,
        vector_store=None,
        knowledge_base=None,
    ):
        self.state_manager = HarnessStateManager(
            session_manager=session_manager, logger=logger
        )
        self.boundary = ExecutionBoundary(logger=logger)
        self.logger = logger
        self._event_emitter = event_emitter
        self._vector_store = vector_store
        self._knowledge_base = knowledge_base

    async def _emit(self, **kwargs) -> None:
        if self._event_emitter:
            try:
                await self._event_emitter(kwargs)
            except Exception as e:
                self.logger.warning(f"bio_harness_emit_failed error={e}")

    async def _persist_stage_result(
        self,
        session_id: str,
        scope_id: Optional[str],
        spec: HarnessStageSpec,
        result: HarnessStageResult,
    ) -> None:
        if self._vector_store is None or not result.output:
            return
        try:
            await self._vector_store.add(
                text=result.output[:4000],
                session_id=session_id,
                owner=spec.agent_id,
                source="bio_workflow_stage",
                namespace="workflow_memory",
                metadata={
                    "namespace": "workflow_memory",
                    "stage": spec.name,
                    "status": result.status,
                    "trace_id": result.trace_id,
                },
                ttl_seconds=0,
                scope_id=scope_id,
            )
        except Exception as e:
            self.logger.warning(
                f"bio_harness_stage_memory_persist_failed stage={spec.name} error={e}"
            )

    async def _persist_workflow_learning(
        self,
        goal: str,
        dataset: str,
        session_id: str,
        trace_id: str,
        scope_id: Optional[str],
        provider_id: Optional[str],
        stage_results: List[HarnessStageResult],
    ) -> None:
        evolution_result = next(
            (
                result
                for result in stage_results
                if result.stage == "evolution" and result.output
            ),
            None,
        )
        if evolution_result is None:
            return

        try:
            from api.routers.evolution_router import EvolutionApproval, get_store

            store = get_store()
            store.append(
                EvolutionApproval(
                    request_id=f"workflow_{trace_id}",
                    agent_id="bio_evolution_agent",
                    changes={
                        "kind": "workflow_retrospective",
                        "scope_id": scope_id,
                        "provider_id": provider_id,
                        "goal": goal,
                        "dataset": dataset,
                        "summary": evolution_result.output[:800],
                        "workflow_trace_id": trace_id,
                        "session_id": session_id,
                    },
                    reason=f"Workflow retrospective for dataset={dataset} and goal={goal[:120]}",
                    status="pending",
                    created_at=datetime.now().isoformat(),
                )
            )
        except Exception as e:
            self.logger.warning(
                f"bio_harness_evolution_approval_persist_failed error={e}"
            )

    def _build_previous_results_payload(
        self,
        stage_results: List[HarnessStageResult],
        depends_on: List[str],
    ) -> Dict[str, Dict[str, Any]]:
        if depends_on:
            relevant = [
                result for result in stage_results if result.stage in depends_on
            ]
        else:
            relevant = stage_results[-2:]

        payload: Dict[str, Dict[str, Any]] = {}
        for result in relevant:
            payload[result.stage] = {
                "status": result.status,
                "trace_id": result.trace_id,
                "elapsed_ms": result.elapsed_ms,
                "output": (result.output or "")[:400],
                "error": result.error,
            }
        return payload

    async def _execute_stage(
        self,
        orchestrator,
        session_id: str,
        workflow_trace_id: str,
        goal: str,
        dataset: str,
        spec: HarnessStageSpec,
        stage_index: int,
        stage_results: List[HarnessStageResult],
        continue_on_error: bool,
        scope_id: Optional[str],
        provider_id: Optional[str],
    ) -> HarnessStageResult:
        stage_trace = f"{workflow_trace_id}-{stage_index}"
        relevant_previous_results = self._build_previous_results_payload(
            stage_results,
            spec.depends_on,
        )
        prev_summary = " | ".join(
            f"{stage}={result['status']}"
            for stage, result in relevant_previous_results.items()
        )
        prompt = spec.prompt.format(
            goal=goal,
            dataset=dataset,
            prev=prev_summary or "none",
        )

        await self._emit(
            event="bio_stage_pending",
            stage=spec.name,
            agent_id=spec.agent_id,
            trace_id=stage_trace,
            session_id=session_id,
            namespace="workflow_runtime",
        )

        self.state_manager.save_checkpoint(
            session_id=session_id,
            trace_id=stage_trace,
            stage_name=spec.name,
            payload={
                "goal": goal,
                "dataset": dataset,
                "agent_id": spec.agent_id,
                "previous_summary": prev_summary,
            },
        )

        await self._emit(
            event="bio_stage_running",
            stage=spec.name,
            agent_id=spec.agent_id,
            trace_id=stage_trace,
            session_id=session_id,
            namespace="workflow_runtime",
        )

        async def emit_stage_progress(elapsed_ms: int):
            progress_pct = min(
                95, int((elapsed_ms / (spec.timeout_seconds * 1000)) * 100)
            )
            await self._emit(
                event="bio_stage_progress",
                stage=spec.name,
                agent_id=spec.agent_id,
                trace_id=stage_trace,
                session_id=session_id,
                namespace="workflow_runtime",
                elapsed_ms=elapsed_ms,
                progress_pct=progress_pct,
                waiting_for="model_response",
                message=f"Waiting for {spec.agent_id} response... {elapsed_ms // 1000}s elapsed",
            )

        boundary_result = await self.boundary.run_with_timeout(
            stage_name=spec.name,
            timeout_seconds=spec.timeout_seconds,
            awaitable=orchestrator.run_single_agent(
                user_input=prompt,
                agent_id=spec.agent_id,
                session_id=session_id,
                trace_id=stage_trace,
                runtime_context={
                    "goal": goal,
                    "dataset": dataset,
                    "scope_id": scope_id,
                    "provider_id": provider_id,
                    "workflow_stage": spec.name,
                    "workflow_trace_id": workflow_trace_id,
                    "knowledge_topic": spec.knowledge_topic or spec.name,
                    "depends_on": spec.depends_on,
                    "previous_results": relevant_previous_results,
                    "execution_policy": {
                        "continue_on_error": continue_on_error,
                        "critical_stage_always_stops": True,
                    },
                },
            ),
            progress_callback=emit_stage_progress,
        )

        result = HarnessStageResult(
            stage=spec.name,
            agent_id=spec.agent_id,
            status=boundary_result["status"],
            elapsed_ms=boundary_result["elapsed_ms"],
            trace_id=stage_trace,
            error=boundary_result["error"],
            output=boundary_result["output"],
            provenance={
                "inputs": {
                    "goal": goal,
                    "dataset": dataset,
                    "scope_id": scope_id,
                    "previous_stages": list(relevant_previous_results.keys()),
                },
                "params": {
                    "timeout_seconds": spec.timeout_seconds,
                    "depends_on": spec.depends_on,
                    "qc_gate": spec.qc_gate,
                    "critical": spec.critical,
                },
                "provider_id": provider_id,
                "elapsed_ms": boundary_result["elapsed_ms"],
            },
        )

        self.state_manager.save_stage_result(
            session_id=session_id,
            trace_id=stage_trace,
            result=result,
        )
        await self._persist_stage_result(session_id, scope_id, spec, result)
        await self._emit(
            event="bio_stage_done",
            stage=spec.name,
            agent_id=spec.agent_id,
            trace_id=stage_trace,
            session_id=session_id,
            namespace="workflow_runtime",
            status=result.status,
            elapsed_ms=result.elapsed_ms,
            output=result.output,
            error=result.error,
        )
        self.logger.info(
            f"bio_harness_stage_done trace_id={stage_trace} stage={spec.name} agent={spec.agent_id} status={result.status} elapsed_ms={result.elapsed_ms}"
        )
        return result

    async def run(
        self,
        orchestrator,
        session_id: str,
        trace_id: str,
        goal: str,
        dataset: str,
        stage_specs: List[HarnessStageSpec],
        continue_on_error: bool,
        scope_id: Optional[str] = None,
        provider_id: Optional[str] = None,
        resume_stage_results: Optional[List[HarnessStageResult]] = None,
    ) -> Dict[str, Any]:
        stage_results: List[HarnessStageResult] = list(resume_stage_results or [])
        critical_failures = 0
        qc_gate_failures = 0
        needs_input_failures = 0
        stopped_by_policy = False
        workflow_user_question: Optional[str] = None
        workflow_required_fields: List[str] = []
        stage_result_map: Dict[str, HarnessStageResult] = {
            r.stage: r for r in stage_results
        }
        stage_index_map = {
            spec.name: idx for idx, spec in enumerate(stage_specs, start=1)
        }
        pending_specs = {
            spec.name: spec for spec in stage_specs if spec.name not in stage_result_map
        }
        running_tasks: Dict[str, asyncio.Task] = {}

        await self._emit(
            event="bio_workflow_start",
            stage="workflow",
            agent_id="harness",
            trace_id=trace_id,
            session_id=session_id,
            namespace="workflow_runtime",
            goal=goal,
            dataset=dataset,
            scope_id=scope_id,
            provider_id=provider_id,
        )

        while pending_specs or running_tasks:
            started_any = False

            for stage_name, spec in list(pending_specs.items()):
                failed_dependencies = [
                    dep
                    for dep in spec.depends_on
                    if dep in stage_result_map and stage_result_map[dep].status != "ok"
                ]
                if failed_dependencies:
                    skipped = HarnessStageResult(
                        stage=spec.name,
                        agent_id=spec.agent_id,
                        status="error",
                        elapsed_ms=0,
                        trace_id=f"{trace_id}-{stage_index_map[spec.name]}",
                        error=f"dependency_failed: {', '.join(failed_dependencies)}",
                        output="",
                    )
                    stage_results.append(skipped)
                    stage_result_map[spec.name] = skipped
                    self.state_manager.save_stage_result(
                        session_id=session_id,
                        trace_id=skipped.trace_id,
                        result=skipped,
                    )
                    await self._emit(
                        event="bio_stage_done",
                        stage=spec.name,
                        agent_id=spec.agent_id,
                        trace_id=skipped.trace_id,
                        session_id=session_id,
                        status=skipped.status,
                        elapsed_ms=0,
                        output="",
                        error=skipped.error,
                    )
                    critical_failures += 1
                    pending_specs.pop(stage_name)
                    if spec.critical or not continue_on_error:
                        stopped_by_policy = True
                    continue

                unresolved_dependencies = [
                    dep for dep in spec.depends_on if dep not in stage_result_map
                ]
                if unresolved_dependencies:
                    continue

                running_tasks[stage_name] = asyncio.create_task(
                    self._execute_stage(
                        orchestrator=orchestrator,
                        session_id=session_id,
                        workflow_trace_id=trace_id,
                        goal=goal,
                        dataset=dataset,
                        spec=spec,
                        stage_index=stage_index_map[spec.name],
                        stage_results=stage_results,
                        continue_on_error=continue_on_error,
                        scope_id=scope_id,
                        provider_id=provider_id,
                    )
                )
                pending_specs.pop(stage_name)
                started_any = True

            if stopped_by_policy and not running_tasks:
                break

            if not running_tasks:
                break

            done, _ = await asyncio.wait(
                running_tasks.values(),
                return_when=asyncio.FIRST_COMPLETED,
            )

            for finished_task in done:
                completed_stage_name = next(
                    name
                    for name, task in running_tasks.items()
                    if task is finished_task
                )
                result = await finished_task
                running_tasks.pop(completed_stage_name)
                stage_results.append(result)
                stage_result_map[result.stage] = result

                if result.status != "ok":
                    critical_failures += 1
                    spec = next(s for s in stage_specs if s.name == result.stage)
                    if spec.critical or not continue_on_error:
                        stopped_by_policy = True

                if result.status == "ok" and result.output:
                    try:
                        import json as _json

                        stage_json = _json.loads(result.output)
                        if (
                            isinstance(stage_json, dict)
                            and stage_json.get("needs_user_input") is True
                        ):
                            needs_input_failures += 1
                            stopped_by_policy = True
                            workflow_user_question = (
                                stage_json.get("user_question")
                                or "Need more information from user before continuing."
                            )
                            workflow_required_fields = stage_json.get(
                                "required_fields", []
                            )
                            await self._emit(
                                event="bio_workflow_needs_input",
                                stage=result.stage,
                                agent_id=result.agent_id,
                                trace_id=trace_id,
                                session_id=session_id,
                                user_question=workflow_user_question,
                                required_fields=workflow_required_fields,
                            )
                    except Exception:
                        pass

                spec = next(s for s in stage_specs if s.name == result.stage)
                if spec.qc_gate and result.status == "ok" and result.output:
                    try:
                        import json as _json

                        qc_output = _json.loads(result.output)
                        qc_overall_pass = qc_output.get("overall_pass", True)
                        qc_critical_failures = qc_output.get("critical_failures", [])
                        if qc_overall_pass is False or qc_critical_failures:
                            self.logger.warning(
                                f"bio_harness_qc_gate_failed stage={result.stage} "
                                f"overall_pass={qc_overall_pass} "
                                f"critical_failures={qc_critical_failures}"
                            )
                            qc_gate_failures += 1
                            stopped_by_policy = True
                            for pending_name, pending_spec in list(
                                pending_specs.items()
                            ):
                                skipped = HarnessStageResult(
                                    stage=pending_spec.name,
                                    agent_id=pending_spec.agent_id,
                                    status="error",
                                    elapsed_ms=0,
                                    trace_id=f"{trace_id}-{stage_index_map[pending_spec.name]}",
                                    error=f"qc_gate_failed: QC stage '{result.stage}' reported failures: {qc_critical_failures or 'overall_pass=False'}",
                                    output="",
                                )
                                stage_results.append(skipped)
                                stage_result_map[skipped.stage] = skipped
                                pending_specs.pop(pending_name)
                                self.state_manager.save_stage_result(
                                    session_id=session_id,
                                    trace_id=skipped.trace_id,
                                    result=skipped,
                                )
                    except Exception:
                        pass

            if stopped_by_policy and not started_any and not running_tasks:
                break

        if stopped_by_policy:
            for stage_name, spec in list(pending_specs.items()):
                skipped = HarnessStageResult(
                    stage=spec.name,
                    agent_id=spec.agent_id,
                    status="error",
                    elapsed_ms=0,
                    trace_id=f"{trace_id}-{stage_index_map[spec.name]}",
                    error=(
                        "needs_user_input"
                        if workflow_user_question
                        else "execution stopped by policy"
                    ),
                    output="",
                )
                stage_results.append(skipped)
                stage_result_map[spec.name] = skipped
                self.state_manager.save_stage_result(
                    session_id=session_id,
                    trace_id=skipped.trace_id,
                    result=skipped,
                )
                await self._emit(
                    event="bio_stage_done",
                    stage=spec.name,
                    agent_id=spec.agent_id,
                    trace_id=skipped.trace_id,
                    session_id=session_id,
                    status=skipped.status,
                    elapsed_ms=0,
                    output="",
                    error=skipped.error,
                )
                pending_specs.pop(stage_name)

        total_failures = critical_failures + qc_gate_failures + needs_input_failures
        await self._emit(
            event="bio_workflow_done",
            stage="workflow",
            agent_id="harness",
            trace_id=trace_id,
            session_id=session_id,
            success=total_failures == 0,
            status=(
                "needs_user_input"
                if workflow_user_question
                else ("success" if total_failures == 0 else "partial_failure")
            ),
            total_stages=len(stage_specs),
            failed_stages=total_failures,
            needs_user_input=workflow_user_question is not None,
            user_question=workflow_user_question,
            required_fields=workflow_required_fields,
        )

        await self._persist_workflow_learning(
            goal=goal,
            dataset=dataset,
            session_id=session_id,
            trace_id=trace_id,
            scope_id=scope_id,
            provider_id=provider_id,
            stage_results=stage_results,
        )

        report_lines = []
        for item in stage_results:
            if item.status == "ok":
                report_lines.append(f"- [{item.stage}] success ({item.elapsed_ms}ms)")
            else:
                report_lines.append(
                    f"- [{item.stage}] {item.status} ({item.elapsed_ms}ms): {item.error}"
                )

        total_failures = critical_failures + qc_gate_failures + needs_input_failures
        return {
            "success": total_failures == 0,
            "status": (
                "needs_user_input"
                if workflow_user_question
                else ("success" if total_failures == 0 else "partial_failure")
            ),
            "response": "\n".join(report_lines),
            "stage_results": [s.to_dict() for s in stage_results],
            "failed_stages": total_failures,
            "total_stages": len(stage_specs),
            "last_checkpoint": self.state_manager.last_checkpoint(session_id),
            "execution_policy": {
                "continue_on_error": continue_on_error,
                "critical_stage_always_stops": True,
                "stopped_by_policy": stopped_by_policy,
                "qc_gate_failures": qc_gate_failures,
                "needs_input_failures": needs_input_failures,
            },
            "scope_id": scope_id,
            "provider_id": provider_id,
            "needs_user_input": workflow_user_question is not None,
            "user_question": workflow_user_question,
            "required_fields": workflow_required_fields,
        }
