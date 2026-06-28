#input_type_name: MarkDuplicateInput
#output_type_name: MarkDuplicateResult
#function_name: mark_alert_duplicate

from pydantic import BaseModel
from lemma_sdk import FunctionContext, Pod


class MarkDuplicateInput(BaseModel):
    alert_id: str
    original_id: str


class MarkDuplicateResult(BaseModel):
    alert_id: str
    status: str


def mark_alert_duplicate(ctx: FunctionContext, data: MarkDuplicateInput) -> MarkDuplicateResult:
    pod = Pod.from_env()
    alert = pod.table("alerts").get(data.alert_id)
    message = alert.get("message") or ""
    suffix = f" [DUPLICATE — linked to {data.original_id}]"
    if suffix.strip() not in message:
        message = (message + suffix)[:2000]
    pod.table("alerts").update(data.alert_id, {
        "status": "correlated",
        "correlation_group": data.original_id,
        "message": message,
    })
    return MarkDuplicateResult(alert_id=data.alert_id, status="correlated")
