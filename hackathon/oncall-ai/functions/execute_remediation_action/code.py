#input_type_name: ExecuteInput
#output_type_name: ExecuteResult
#function_name: execute_remediation_action

from datetime import datetime, timezone

from pydantic import BaseModel
from lemma_sdk import FunctionContext, Pod


class ExecuteInput(BaseModel):
    incident_id: str


class ExecuteResult(BaseModel):
    action_id: str | None = None
    success: bool
    output: str
    executed_at: str


def execute_remediation_action(ctx: FunctionContext, data: ExecuteInput) -> ExecuteResult:
    """STUB — Day 4 will add real kubectl/API execution simulation. For now: select the
    highest-confidence approved action for the incident and return simulated output."""
    pod = Pod.from_env()
    rows = pod.records.list(
        "remediation_actions",
        limit=50,
        filter=[
            {"field": "incident_id", "op": "eq", "value": data.incident_id},
            {"field": "status", "op": "eq", "value": "approved"},
        ],
        sort=[{"field": "confidence", "direction": "desc"}],
    ).to_dict()["items"]

    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    if not rows:
        return ExecuteResult(
            action_id=None,
            success=False,
            output="STUB: No approved remediation action found for this incident.",
            executed_at=now,
        )

    action = rows[0]
    return ExecuteResult(
        action_id=str(action.get("id")),
        success=True,
        output=(f"STUB: Simulated execution of '{action.get('action_type')}' — "
                f"{action.get('description')}. Command completed successfully."),
        executed_at=now,
    )
