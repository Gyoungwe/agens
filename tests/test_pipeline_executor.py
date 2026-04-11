import logging
import pytest

from core.pipeline_executor import PipelineExecutor, PipelineRunResult


class FakeLogger:
    def info(self, msg):
        pass

    def warning(self, msg):
        pass


@pytest.mark.asyncio
async def test_pipeline_executor_nextflow_reports_error_on_missing_script():
    executor = PipelineExecutor(logger=FakeLogger())
    # Empty script triggers FileNotFoundError (no nextflow binary), not timeout
    result = await executor.run(
        {
            "engine": "nextflow",
            "nextflow_script": "",
            "params": {},
        },
        timeout_seconds=5,
    )
    assert result.success is False
    assert result.exit_code == -1
    assert result.error is not None
    assert (
        "Nextflow not found" in result.error
        or "not found" in result.error
        or "No pipeline script" in result.error
    )


@pytest.mark.asyncio
async def test_pipeline_executor_rejects_empty_spec():
    executor = PipelineExecutor(logger=FakeLogger())
    result = await executor.run({})
    assert result.success is False
    assert "No pipeline script" in (result.error or "")


@pytest.mark.asyncio
async def test_pipeline_executor_snakemake_not_found_gives_helpful_error():
    executor = PipelineExecutor(logger=FakeLogger())
    result = await executor.run(
        {
            "engine": "snakemake",
            "snakemake_script": "rule all:\n    output: 'out.txt'\n    shell: 'echo done > out.txt'",
            "params": {},
        },
        timeout_seconds=5,
    )
    assert result.success is False
    assert result.exit_code == -1
    assert "Snakemake not found" in result.error or "not found" in result.error


@pytest.mark.asyncio
async def test_pipeline_executor_result_structure():
    result = PipelineRunResult(
        success=True,
        engine="nextflow",
        exit_code=0,
        stdout="done",
        stderr="",
        work_dir="/tmp/test",
        outputs={"outdir": "/tmp/test/results"},
        error=None,
    )
    assert result.success is True
    assert result.engine == "nextflow"
    assert result.exit_code == 0
    assert result.outputs["outdir"] == "/tmp/test/results"
