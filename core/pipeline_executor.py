import asyncio
import os
import subprocess
import tempfile
from dataclasses import dataclass
from typing import Any, Dict, List, Optional


@dataclass
class PipelineRunResult:
    success: bool
    engine: str
    exit_code: int
    stdout: str
    stderr: str
    work_dir: str
    outputs: Dict[str, str]
    error: Optional[str]


class PipelineExecutor:
    def __init__(self, logger=None):
        self.logger = logger

    def _info(self, msg: str) -> None:
        if self.logger:
            self.logger.info(msg)

    def _warn(self, msg: str) -> None:
        if self.logger:
            self.logger.warning(msg)

    async def run(
        self,
        spec: Dict[str, Any],
        timeout_seconds: int = 3600,
    ) -> PipelineRunResult:
        engine = spec.get("engine", "nextflow")
        nextflow_script = spec.get("nextflow_script", "")
        snakemake_script = spec.get("snakemake_script", "")
        params = spec.get("params", {})
        entrypoint = spec.get("entrypoint", "")

        if not nextflow_script and not snakemake_script:
            return PipelineRunResult(
                success=False,
                engine=engine,
                exit_code=-1,
                stdout="",
                stderr="",
                work_dir="",
                outputs={},
                error="No pipeline script provided in PipelineArtifactSpec",
            )

        with tempfile.TemporaryDirectory(prefix="bio_pipeline_") as tmpdir:
            if engine == "nextflow" and nextflow_script:
                return await self._run_nextflow(
                    nextflow_script, params, tmpdir, timeout_seconds
                )
            elif engine == "snakemake" and snakemake_script:
                return await self._run_snakemake(
                    snakemake_script, params, tmpdir, timeout_seconds
                )
            else:
                return PipelineRunResult(
                    success=False,
                    engine=engine,
                    exit_code=-1,
                    stdout="",
                    stderr="",
                    work_dir=tmpdir,
                    outputs={},
                    error=f"Unsupported engine '{engine}' or missing script",
                )

    async def _run_nextflow(
        self,
        script: str,
        params: Dict[str, str],
        work_dir: str,
        timeout_seconds: int,
    ) -> PipelineRunResult:
        script_path = os.path.join(work_dir, "pipeline.nf")
        with open(script_path, "w") as f:
            f.write(script)

        cmd = ["nextflow", "run", script_path]
        for k, v in params.items():
            cmd.extend([f"--{k}", str(v)])

        self._info(f"bio_pipeline_executor running nextflow: {' '.join(cmd)}")

        try:
            proc = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                cwd=work_dir,
                env={**os.environ, "NXF_HOME": os.path.join(work_dir, ".nextflow")},
            )
            try:
                stdout_b, stderr_b = await asyncio.wait_for(
                    proc.communicate(), timeout=timeout_seconds
                )
            except asyncio.TimeoutError:
                proc.kill()
                await proc.wait()
                return PipelineRunResult(
                    success=False,
                    engine="nextflow",
                    exit_code=-1,
                    stdout="",
                    stderr="",
                    work_dir=work_dir,
                    outputs={},
                    error=f"Pipeline timed out after {timeout_seconds}s",
                )

            stdout = stdout_b.decode("utf-8", errors="replace") if stdout_b else ""
            stderr = stderr_b.decode("utf-8", errors="replace") if stderr_b else ""

            outputs = self._parse_nextflow_outputs(stdout, work_dir)

            if proc.returncode == 0:
                self._info(f"bio_pipeline_executor nextflow completed successfully")
            else:
                self._warn(
                    f"bio_pipeline_executor nextflow failed with exit {proc.returncode}"
                )

            return PipelineRunResult(
                success=proc.returncode == 0,
                engine="nextflow",
                exit_code=proc.returncode or 0,
                stdout=stdout,
                stderr=stderr,
                work_dir=work_dir,
                outputs=outputs,
                error=None if proc.returncode == 0 else f"Exit code {proc.returncode}",
            )
        except FileNotFoundError:
            self._warn("bio_pipeline_executor nextflow not found in PATH")
            return PipelineRunResult(
                success=False,
                engine="nextflow",
                exit_code=-1,
                stdout="",
                stderr="",
                work_dir=work_dir,
                outputs={},
                error=(
                    "Nextflow not found. Install: curl -s https://get.nextflow.io | bash\n"
                    "Or: conda install -c bioconda nextflow"
                ),
            )
        except Exception as e:
            return PipelineRunResult(
                success=False,
                engine="nextflow",
                exit_code=-1,
                stdout="",
                stderr="",
                work_dir=work_dir,
                outputs={},
                error=f"{type(e).__name__}: {e}",
            )

    async def _run_snakemake(
        self,
        script: str,
        params: Dict[str, str],
        work_dir: str,
        timeout_seconds: int,
    ) -> PipelineRunResult:
        script_path = os.path.join(work_dir, "Snakefile")
        with open(script_path, "w") as f:
            f.write(script)

        cmd = ["snakemake", "--cores", str(params.get("cores", 4))]
        for k, v in params.items():
            if k not in ("cores", "snakefile"):
                cmd.extend([f"--{k}", str(v)])

        self._info(f"bio_pipeline_executor running snakemake: {' '.join(cmd)}")

        try:
            proc = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                cwd=work_dir,
            )
            try:
                stdout_b, stderr_b = await asyncio.wait_for(
                    proc.communicate(), timeout=timeout_seconds
                )
            except asyncio.TimeoutError:
                proc.kill()
                await proc.wait()
                return PipelineRunResult(
                    success=False,
                    engine="snakemake",
                    exit_code=-1,
                    stdout="",
                    stderr="",
                    work_dir=work_dir,
                    outputs={},
                    error=f"Pipeline timed out after {timeout_seconds}s",
                )

            stdout = stdout_b.decode("utf-8", errors="replace") if stdout_b else ""
            stderr = stderr_b.decode("utf-8", errors="replace") if stderr_b else ""

            return PipelineRunResult(
                success=proc.returncode == 0,
                engine="snakemake",
                exit_code=proc.returncode or 0,
                stdout=stdout,
                stderr=stderr,
                work_dir=work_dir,
                outputs={},
                error=None if proc.returncode == 0 else f"Exit code {proc.returncode}",
            )
        except FileNotFoundError:
            self._warn("bio_pipeline_executor snakemake not found in PATH")
            return PipelineRunResult(
                success=False,
                engine="snakemake",
                exit_code=-1,
                stdout="",
                stderr="",
                work_dir=work_dir,
                outputs={},
                error="Snakemake not found. Install: conda install -c bioconda snakemake",
            )
        except Exception as e:
            return PipelineRunResult(
                success=False,
                engine="snakemake",
                exit_code=-1,
                stdout="",
                stderr="",
                work_dir=work_dir,
                outputs={},
                error=f"{type(e).__name__}: {e}",
            )

    def _parse_nextflow_outputs(self, stdout: str, work_dir: str) -> Dict[str, str]:
        outputs = {}
        if not stdout:
            return outputs
        output_markers = [
            "results/",
            "output/",
            "outdir=",
        ]
        for line in stdout.splitlines():
            lower = line.lower()
            for marker in output_markers:
                if marker in lower:
                    parts = line.split("=", 1)
                    if len(parts) == 2:
                        outputs[parts[0].strip()] = parts[1].strip()
                    break
        return outputs
