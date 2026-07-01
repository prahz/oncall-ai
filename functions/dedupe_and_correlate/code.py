#input_type_name: DedupeInput
#output_type_name: DedupeResult
#function_name: dedupe_and_correlate

from typing import Optional
from pydantic import BaseModel
from lemma_sdk import FunctionContext, Pod


class DedupeInput(BaseModel):
    alert_id: str


class DedupeResult(BaseModel):
    decision: str                 # "attached" | "new_incident"
    incident_id: Optional[str] = None
    is_duplicate: bool = False
    reason: str = ""


async def dedupe_and_correlate(ctx: FunctionContext, data: DedupeInput) -> DedupeResult:
    pod = Pod.from_env()
    alerts = pod.table("alerts")
    alert = alerts.get(data.alert_id)
    service = alert.get("service")

    # Look at recent alerts for the same service (most recent first).
    recent = pod.records.list(
        "alerts", limit=50,
        filter=[{"field": "service", "op": "eq", "value": service}],
        sort=[{"field": "created_at", "direction": "desc"}],
    ).to_dict()["items"]

    # 1) Duplicate: a recent alert on the same service+metric that is already on an incident.
    for a in recent:
        if a["id"] == alert["id"]:
            continue
        if a.get("metric") == alert.get("metric") and a.get("incident_id"):
            alerts.update(alert["id"], {
                "status": "correlated",
                "incident_id": a["incident_id"],
                "correlation_group": a.get("correlation_group") or str(a["incident_id"]),
            })
            return DedupeResult(
                decision="attached", incident_id=str(a["incident_id"]), is_duplicate=True,
                reason=f"Duplicate of a recent {service}/{alert.get('metric')} alert",
            )

    # 2) Any open (not yet resolved) incident for this service? Attach to it.
    open_incidents = pod.records.list(
        "incidents", limit=20,
        filter=[
            {"field": "service", "op": "eq", "value": service},
            {"field": "status", "op": "ne", "value": "resolved"},
        ],
        sort=[{"field": "created_at", "direction": "desc"}],
    ).to_dict()["items"]

    if open_incidents:
        inc = open_incidents[0]
        alerts.update(alert["id"], {
            "status": "correlated",
            "incident_id": inc["id"],
            "correlation_group": str(inc.get("number") or inc["id"]),
        })
        return DedupeResult(
            decision="attached", incident_id=str(inc["id"]),
            reason=f"Attached to open incident #{inc.get('number')} for {service}",
        )

    # 3) Nothing to attach to -> a new incident should be created by the workflow.
    alerts.update(alert["id"], {"correlation_group": f"grp-{str(alert['id'])[:8]}"})
    return DedupeResult(decision="new_incident", reason=f"No open incident for {service}")
