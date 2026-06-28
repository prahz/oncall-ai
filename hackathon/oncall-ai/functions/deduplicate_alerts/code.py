#input_type_name: DeduplicateInput
#output_type_name: DeduplicateResult
#function_name: deduplicate_alerts

from datetime import datetime, timedelta, timezone

from pydantic import BaseModel
from lemma_sdk import FunctionContext, Pod


class DeduplicateInput(BaseModel):
    new_alert_id: str


class DeduplicateResult(BaseModel):
    is_duplicate: bool
    original_id: str | None = None
    reason: str


def _parse_ts(value):
    if not value:
        return None
    try:
        return datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except ValueError:
        return None


def deduplicate_alerts(ctx: FunctionContext, data: DeduplicateInput) -> DeduplicateResult:
    """STUB — Day 4 will implement real similarity comparison. For now: flag as
    duplicate only if the exact same service+metric already exists with status != 'new'
    in the last 30 minutes."""
    pod = Pod.from_env()
    new_alert = pod.table("alerts").get(data.new_alert_id)
    service = new_alert.get("service")
    metric = new_alert.get("metric")

    candidates = pod.records.list(
        "alerts",
        limit=200,
        filter=[
            {"field": "service", "op": "eq", "value": service},
            {"field": "metric", "op": "eq", "value": metric},
        ],
    ).to_dict()["items"]

    cutoff = datetime.now(timezone.utc) - timedelta(minutes=30)
    for existing in candidates:
        if existing.get("id") == data.new_alert_id:
            continue
        if existing.get("status") == "new":
            continue
        ts = _parse_ts(existing.get("timestamp")) or _parse_ts(existing.get("created_at"))
        if ts is not None and ts < cutoff:
            continue
        return DeduplicateResult(
            is_duplicate=True,
            original_id=str(existing.get("id")),
            reason=f"Duplicate of {existing.get('id')} — same service and metric within 30 min window",
        )

    return DeduplicateResult(is_duplicate=False, reason="No duplicate found")
