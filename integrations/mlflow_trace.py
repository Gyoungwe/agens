import logging
import os
import time
from typing import Dict, List, Optional

logger = logging.getLogger(__name__)


class TraceMLflowTracker:
    """Optional MLflow trace-level observability tracker."""

    def __init__(self):
        self.enabled = os.getenv("ENABLE_MLFLOW_TRACE", "false").lower() == "true"
        self._mlflow = None
        self._client = None
        self._experiment_id: Optional[str] = None
        self._run_ids: Dict[str, str] = {}

        if not self.enabled:
            return

        try:
            import mlflow
            from mlflow.tracking import MlflowClient

            self._mlflow = mlflow
            self._client = MlflowClient()
            tracking_uri = os.getenv("MLFLOW_TRACKING_URI")
            experiment_name = os.getenv("MLFLOW_EXPERIMENT", "agens-agent-system")

            if tracking_uri:
                self._mlflow.set_tracking_uri(tracking_uri)
            self._mlflow.set_experiment(experiment_name)

            exp = self._mlflow.get_experiment_by_name(experiment_name)
            self._experiment_id = exp.experiment_id if exp else None
            logger.info(
                f"📈 TraceMLflowTracker enabled (experiment={experiment_name}, tracking_uri={tracking_uri or 'default'})"
            )
        except Exception as e:
            self.enabled = False
            logger.warning(f"TraceMLflowTracker disabled: {e}")

    def _get_run_id(self, trace_id: str) -> Optional[str]:
        return self._run_ids.get(trace_id)

    def start_trace(
        self,
        trace_id: str,
        user_input: str,
        session_id: Optional[str],
        plan: List[dict],
    ):
        if not self.enabled or not self._client or not self._experiment_id:
            return

        try:
            run = self._client.create_run(
                experiment_id=self._experiment_id,
                tags={
                    "trace_id": trace_id,
                    "component": "orchestrator",
                    "entrypoint": "run",
                },
            )
            run_id = run.info.run_id
            self._run_ids[trace_id] = run_id

            self._client.log_param(run_id, "trace_id", trace_id)
            self._client.log_param(run_id, "session_id", session_id or "")
            self._client.log_param(run_id, "input_length", str(len(user_input or "")))
            self._client.log_param(run_id, "planned_agents", str(len(plan or [])))
            self._client.log_metric(run_id, "planned_tasks", float(len(plan or [])))
        except Exception as e:
            logger.debug(f"TraceMLflowTracker start_trace degraded: {e}")

    def log_dispatch(self, trace_id: str, agent_id: str):
        run_id = self._get_run_id(trace_id)
        if not self.enabled or not self._client or not run_id:
            return

        try:
            ts = int(time.time() * 1000)
            self._client.log_metric(run_id, "dispatched_tasks", 1.0, timestamp=ts)
            self._client.set_tag(run_id, f"dispatch_{agent_id}", "true")
        except Exception as e:
            logger.debug(f"TraceMLflowTracker log_dispatch degraded: {e}")

    def log_agent_result(self, trace_id: str, agent_id: str, success: bool):
        run_id = self._get_run_id(trace_id)
        if not self.enabled or not self._client or not run_id:
            return

        try:
            ts = int(time.time() * 1000)
            metric_name = f"agent_{agent_id}_success"
            self._client.log_metric(
                run_id, metric_name, 1.0 if success else 0.0, timestamp=ts
            )
            self._client.log_metric(run_id, "completed_tasks", 1.0, timestamp=ts)
        except Exception as e:
            logger.debug(f"TraceMLflowTracker log_agent_result degraded: {e}")

    def finish_trace(
        self,
        trace_id: str,
        status: str,
        elapsed_ms: int,
        results_count: int,
        final_length: int = 0,
        error: str = "",
    ):
        run_id = self._get_run_id(trace_id)
        if not self.enabled or not self._client or not run_id:
            return

        try:
            self._client.log_metric(run_id, "elapsed_ms", float(elapsed_ms))
            self._client.log_metric(run_id, "results_count", float(results_count))
            self._client.log_metric(run_id, "final_length", float(final_length))
            self._client.set_tag(run_id, "status", status)
            if error:
                self._client.set_tag(run_id, "error", error[:500])
            self._client.set_terminated(run_id, status="FINISHED")
        except Exception as e:
            logger.debug(f"TraceMLflowTracker finish_trace degraded: {e}")
        finally:
            self._run_ids.pop(trace_id, None)

    def list_recent_traces(self, limit: int = 20) -> List[dict]:
        if not self.enabled or not self._client or not self._experiment_id:
            return []

        try:
            runs = self._client.search_runs(
                experiment_ids=[self._experiment_id],
                filter_string="tags.component = 'orchestrator'",
                run_view_type=1,
                max_results=max(1, min(limit, 100)),
                order_by=["attributes.start_time DESC"],
            )

            traces: List[dict] = []
            for run in runs:
                info = run.info
                data = run.data
                traces.append(
                    {
                        "trace_id": data.params.get("trace_id", ""),
                        "run_id": info.run_id,
                        "status": (
                            data.tags.get("status") or info.status or ""
                        ).lower(),
                        "session_id": data.params.get("session_id", ""),
                        "planned_tasks": int(
                            float(data.metrics.get("planned_tasks", 0))
                        ),
                        "completed_tasks": int(
                            float(data.metrics.get("completed_tasks", 0))
                        ),
                        "elapsed_ms": int(float(data.metrics.get("elapsed_ms", 0))),
                        "results_count": int(
                            float(data.metrics.get("results_count", 0))
                        ),
                        "final_length": int(float(data.metrics.get("final_length", 0))),
                        "start_time": info.start_time,
                        "end_time": info.end_time,
                    }
                )

            return traces
        except Exception as e:
            logger.debug(f"TraceMLflowTracker list_recent_traces degraded: {e}")
            return []


_tracker: Optional[TraceMLflowTracker] = None


def get_trace_tracker() -> TraceMLflowTracker:
    global _tracker
    if _tracker is None:
        _tracker = TraceMLflowTracker()
    return _tracker
