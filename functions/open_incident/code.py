#input_type_name: OpenIncidentInput
#output_type_name: OpenIncidentResult
#function_name: open_incident

from datetime import datetime, timezone
from typing import List
from pydantic import BaseModel, Field
from lemma_sdk import FunctionContext, Pod

ORDER = ["low", "medium", "high", "critical"]
RANK = {name: i for i, name in enumerate(ORDER)}
MIN_CONFIDENCE = 0.9          # autonomy dial: min confidence to auto-approve
AUTO_MAX_SEVERITY = "high"    # never auto-approve above this severity


class OpenIncidentInput(BaseModel):
    alert_id: str
    title: str
    root_cause: str = ""
    blast_radius: str = "single_service"
    suggested_fix: str = ""
    action_type: str = "manual_fix_required"
    confidence: float = 0.5
    suspect_deploy: str = "unknown"
    affected_services: List[str] = Field(default_factory=list)


class OpenIncidentResult(BaseModel):
    incident_id: str
    incident_number: int
    remediation_action_id: str
    final_severity: str
    auto_approve_eligible: bool
    runbook_safe: bool
    reason: str


def _runbook_safe(pod: Pod, service: str) -> bool:
    """Deterministically parse /runbooks/<service>.md for the 'Auto-remediation safe:' line."""
    try:
        raw = pod.files.download(f"/runbooks/{service}.md")
        text = raw.decode("utf-8") if isinstance(raw, (bytes, bytearray)) else str(raw)
    except Exception:
        return False
    for line in text.splitlines():
        if "auto-remediation safe" in line.lower():
            return "yes" in line.lower()
    return False


async def open_incident(ctx: FunctionContext, data: OpenIncidentInput) -> OpenIncidentResult:
    pod = Pod.from_env()
    alert = pod.table("alerts").get(data.alert_id)
    service = alert.get("service") or "unknown"

    # --- SAFETY-CRITICAL VALUES ARE DETERMINISTIC, never trusted from the LLM ---
    raw_severity = alert.get("severity") or "high"        # from the alert row
    runbook_safe = _runbook_safe(pod, service)            # parsed from the runbook file

    # Triage scoring: escalate only (never downgrade the alert's real severity).
    base = {"critical": 40, "high": 25, "medium": 10, "low": 0}
    radius = {"single_service": 10, "multi_service": 25, "infrastructure": 40}
    score = base.get(raw_severity, 0) + radius.get(data.blast_radius, 0)
    if 0 <= datetime.now(timezone.utc).hour <= 6:
        score += 15
    score_sev = "critical" if score >= 70 else "high" if score >= 45 else "medium" if score >= 20 else "low"
    final = ORDER[max(RANK.get(raw_severity, 1), RANK[score_sev])]

    auto_ok = (
        final != "critical"
        and RANK[final] <= RANK[AUTO_MAX_SEVERITY]
        and data.confidence >= MIN_CONFIDENCE
        and runbook_safe
    )
    if final == "critical":
        reason = "Critical incident: human approval always required"
    elif not runbook_safe:
        reason = "Runbook does not mark this remediation auto-safe"
    elif data.confidence < MIN_CONFIDENCE:
        reason = f"Confidence {data.confidence:.2f} below {MIN_CONFIDENCE:.2f}"
    elif auto_ok:
        reason = "Safe runbook + high confidence + non-critical: auto-approved"
    else:
        reason = "Does not meet auto-approval rules"

    # Create the incident.
    incident = pod.table("incidents").create({
        "title": data.title,
        "service": service,
        "severity": final,
        "status": "triaging",
        "blast_radius": data.blast_radius,
        "root_cause": data.root_cause,
        "confidence": data.confidence,
        "suggested_fix": data.suggested_fix,
        "suspect_deploy": data.suspect_deploy,
        "affected_services": data.affected_services or [service],
        "triggering_alerts": [data.alert_id],
    })
    incident_id = str(incident["id"])

    # Link the triggering alert to the incident.
    pod.table("alerts").update(data.alert_id, {"incident_id": incident_id, "status": "triaged"})

    # Create the remediation action (the row the approval gate acts on).
    action = pod.table("remediation_actions").create({
        "incident_id": incident_id,
        "action_type": data.action_type,
        "description": data.suggested_fix or data.action_type,
        "confidence": data.confidence,
        "auto_approved": auto_ok,
        "status": "approved" if auto_ok else "pending_approval",
    })

    return OpenIncidentResult(
        incident_id=incident_id,
        incident_number=int(incident.get("number") or 0),
        remediation_action_id=str(action["id"]),
        final_severity=final,
        auto_approve_eligible=auto_ok,
        runbook_safe=runbook_safe,
        reason=reason,
    )
