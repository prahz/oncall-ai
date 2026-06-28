#input_type_name: ApproveTopInput
#output_type_name: ApproveTopResult
#function_name: approve_top_remediation

from pydantic import BaseModel
from lemma_sdk import FunctionContext, Pod


class ApproveTopInput(BaseModel):
    incident_id: str
    approver_email: str = ""


class ApproveTopResult(BaseModel):
    action_id: str | None = None
    approved: bool
    reason: str


def approve_top_remediation(ctx: FunctionContext, data: ApproveTopInput) -> ApproveTopResult:
    """Approve the highest-confidence pending_approval action for the incident. The
    resulting status=approved UPDATE fires the auto_remediation_workflow trigger."""
    pod = Pod.from_env()
    rows = pod.records.list(
        "remediation_actions",
        limit=50,
        filter=[
            {"field": "incident_id", "op": "eq", "value": data.incident_id},
            {"field": "status", "op": "eq", "value": "pending_approval"},
        ],
        sort=[{"field": "confidence", "direction": "desc"}],
    ).to_dict()["items"]

    if not rows:
        return ApproveTopResult(action_id=None, approved=False,
                                reason="No pending_approval action found for this incident")
    action = rows[0]
    pod.table("remediation_actions").update(action["id"], {
        "status": "approved",
        "executed_by": data.approver_email or "human",
    })
    return ApproveTopResult(action_id=str(action["id"]), approved=True,
                            reason="Approved highest-confidence pending action")
