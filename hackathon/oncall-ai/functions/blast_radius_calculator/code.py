#input_type_name: BlastRadiusInput
#output_type_name: BlastRadiusResult
#function_name: blast_radius_calculator

from datetime import datetime, timedelta, timezone

from pydantic import BaseModel
from lemma_sdk import FunctionContext, Pod


class BlastRadiusInput(BaseModel):
    service: str
    window_minutes: int = 15


class BlastRadiusResult(BaseModel):
    blast_radius: str
    affected_services: list[str]


def _parse_ts(value):
    if not value:
        return None
    try:
        return datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except ValueError:
        return None


def blast_radius_calculator(ctx: FunctionContext, data: BlastRadiusInput) -> BlastRadiusResult:
    """STUB — Day 4 will implement real dependency graph traversal. For now: count
    distinct services among recent active alerts to determine radius."""
    pod = Pod.from_env()
    affected = {data.service}
    cutoff = datetime.now(timezone.utc) - timedelta(minutes=data.window_minutes)

    rows = pod.records.list("alerts", limit=500).to_dict()["items"]
    for alert in rows:
        if alert.get("status") not in ("correlated", "new"):
            continue
        ts = _parse_ts(alert.get("timestamp")) or _parse_ts(alert.get("created_at"))
        if ts is not None and ts < cutoff:
            continue
        if alert.get("service"):
            affected.add(alert["service"])

    count = len(affected)
    if count == 1:
        radius = "single_service"
    elif count <= 3:
        radius = "multi_service"
    else:
        radius = "infrastructure"
    return BlastRadiusResult(blast_radius=radius, affected_services=sorted(affected))
