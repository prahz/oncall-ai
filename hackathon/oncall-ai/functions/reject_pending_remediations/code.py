#input_type_name: RejectInput
#output_type_name: RejectResult
#function_name: reject_pending_remediations

from pydantic import BaseModel
from lemma_sdk import FunctionContext, Pod


class RejectInput(BaseModel):
    incident_id: str
    approver_email: str = ""


class RejectResult(BaseModel):
    rejected_count: int


def reject_pending_remediations(ctx: FunctionContext, data: RejectInput) -> RejectResult:
    pod = Pod.from_env()
    rows = pod.records.list(
        "remediation_actions",
        limit=100,
        filter=[
            {"field": "incident_id", "op": "eq", "value": data.incident_id},
            {"field": "status", "op": "eq", "value": "pending_approval"},
        ],
    ).to_dict()["items"]

    updates = []
    for row in rows:
        updates.append({
            "id": row["id"],
            "status": "rejected",
            "executed_by": data.approver_email or "human",
        })
    if updates:
        pod.records.bulk_update("remediation_actions", updates)
    return RejectResult(rejected_count=len(updates))
