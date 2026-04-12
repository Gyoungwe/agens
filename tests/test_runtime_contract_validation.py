import pytest
from pydantic import ValidationError

from core.runtime_contract import (
    RuntimeDelegationDecisionContract,
    RUNTIME_CONTRACT_VERSION,
    RuntimeCitationContract,
    RuntimeEventContract,
    RuntimeMemoryRecordContract,
    RuntimeMessageContract,
    RuntimeOutputContract,
    RuntimeResultPayloadContract,
    RuntimeSessionContract,
    RuntimeTaskPayloadContract,
    RuntimeWorkflowBoundaryContract,
)


def test_runtime_contract_models_default_to_current_version():
    session = RuntimeSessionContract(
        session_id="sess-1",
        title="Test",
        namespace="chat_session",
        created_at="2026-01-01T00:00:00",
        updated_at="2026-01-01T00:00:00",
    )
    message = RuntimeMessageContract(
        id="msg-1",
        created_at="2026-01-01T00:00:00",
        sender="a",
        recipient="b",
        type="task",
        trace_id="trace-1",
    )
    task = RuntimeTaskPayloadContract(instruction="run")
    result = RuntimeResultPayloadContract(success=True, output="ok")
    memory = RuntimeMemoryRecordContract(id="m1", text="x", namespace="chat_memory")
    event = RuntimeEventContract(
        event_id="evt-1",
        task_id="task-1",
        created_at=1.0,
        type="agent_start",
        agent="agent-a",
        status="started",
    )
    citation = RuntimeCitationContract(text="paper-a")
    output = RuntimeOutputContract(namespace="research_runtime", content="report")
    workflow = RuntimeWorkflowBoundaryContract()
    delegation = RuntimeDelegationDecisionContract(mode="direct_chat")

    for model in [
        session,
        message,
        task,
        result,
        memory,
        event,
        citation,
        output,
        workflow,
        delegation,
    ]:
        assert model.contract_version == RUNTIME_CONTRACT_VERSION


def test_runtime_contract_rejects_invalid_session_namespace():
    with pytest.raises(ValidationError):
        RuntimeSessionContract(
            session_id="sess-1",
            title="Test",
            namespace="invalid_session",
            created_at="2026-01-01T00:00:00",
            updated_at="2026-01-01T00:00:00",
        )


def test_runtime_contract_rejects_invalid_runtime_namespace():
    with pytest.raises(ValidationError):
        RuntimeOutputContract(namespace="invalid_runtime", content="bad")


def test_runtime_contract_rejects_invalid_memory_namespace():
    with pytest.raises(ValidationError):
        RuntimeMemoryRecordContract(id="m1", text="x", namespace="invalid_memory")


def test_runtime_contract_rejects_invalid_delegation_mode():
    with pytest.raises(ValidationError):
        RuntimeDelegationDecisionContract(mode="invalid_mode")
