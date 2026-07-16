#input_type_name: OpenIncidentInput
#output_type_name: OpenIncidentResult
#function_name: open_incident

from datetime import datetime, timezone
from typing import List
from pydantic import BaseModel, Field
from lemma_sdk import FunctionContext, Pod

ORDER = ["low", "medium", "high", "critical"]
RANK = {name: i for i, name in enumerate(ORDER)}

# --- Autonomy dials (all deterministic; the LLM never sets these) -------------
MIN_CONFIDENCE = 0.85         # analyst must be at least this sure of the fix
# Auto-remediation is blocked for anything at/above this severity...
AUTO_BLOCK_SEVERITY = "critical"
# ...or with a blast radius this wide.
AUTO_BLOCK_BLAST = "infrastructure"


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
    triage_score: int
    triage_reason: str
    auto_approve_eligible: bool
    runbook_safe: bool
    reason: str


def _runbook_safe(pod: Pod, service: str) -> bool:
    """Deterministic auto-remediation verdict, read straight from the runbooks
    table (`auto_safe`). No matching runbook => not safe."""
    try:
        rows = pod.records.list(
            "runbooks", limit=1,
            filter=[{"field": "service", "op": "eq", "value": service}],
        ).to_dict()["items"]
    except Exception:
        return False
    return bool(rows and rows[0].get("auto_safe"))


def _triage(raw_severity: str, blast_radius: str, confidence: float,
            hour_utc: int) -> tuple[int, str, list[str]]:
    """Transparent, additive triage score (0-100) with a per-factor breakdown.
    Nothing here is a black box: each line of the breakdown is a number a human
    can check. Scoring only ESCALATES severity, it never downgrades a real one."""
    breakdown: list[str] = []

    sev_pts = {"critical": 50, "high": 30, "medium": 15, "low": 5}
    s = sev_pts.get(raw_severity, 15)
    breakdown.append(f"severity {raw_severity} = +{s}")
    score = s

    blast_pts = {"single_service": 0, "multi_service": 15, "infrastructure": 30}
    b = blast_pts.get(blast_radius, 0)
    if b:
        breakdown.append(f"blast radius {blast_radius} = +{b}")
    score += b

    if 0 <= hour_utc <= 6:
        breakdown.append("off-hours (00:00-06:00 UTC, fewer humans awake) = +10")
        score += 10

    if confidence < 0.6:
        breakdown.append(f"low analyst confidence ({confidence:.0%}) adds risk = +10")
        score += 10

    score = max(0, min(100, score))

    band = ("critical" if score >= 70 else "high" if score >= 45
            else "medium" if score >= 25 else "low")
    final = ORDER[max(RANK.get(raw_severity, 1), RANK[band])]
    breakdown.append(f"score {score}/100 -> band {band}; final severity "
                     f"max({raw_severity}, {band}) = {final}")
    return score, final, breakdown


async def open_incident(ctx: FunctionContext, data: OpenIncidentInput) -> OpenIncidentResult:
    pod = Pod.from_env()
    alert = pod.table("alerts").get(data.alert_id)
    service = alert.get("service") or "unknown"

    # --- SAFETY-CRITICAL VALUES ARE DETERMINISTIC, never trusted from the LLM ---
    raw_severity = alert.get("severity") or "high"        # from the alert row
    runbook_safe = _runbook_safe(pod, service)            # parsed from the runbook file
    hour_utc = datetime.now(timezone.utc).hour

    score, final, breakdown = _triage(raw_severity, data.blast_radius,
                                      data.confidence, hour_utc)
    triage_reason = " · ".join(breakdown)

    # --- Deterministic auto-approval gate (every clause is explainable) --------
    gates = {
        "runbook marks it auto-safe": runbook_safe,
        f"confidence >= {MIN_CONFIDENCE:.0%}": data.confidence >= MIN_CONFIDENCE,
        "not critical severity": final != AUTO_BLOCK_SEVERITY,
        "blast radius not infrastructure-wide": data.blast_radius != AUTO_BLOCK_BLAST,
    }
    auto_ok = all(gates.values())
    failed = [name for name, ok in gates.items() if not ok]
    if auto_ok:
        reason = "Auto-approved — all safety gates passed: " + "; ".join(gates.keys())
    else:
        reason = "Human approval required — failed gate(s): " + "; ".join(failed)

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
        "triage_score": score,
        "triage_reason": triage_reason,
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
        triage_score=score,
        triage_reason=triage_reason,
        auto_approve_eligible=auto_ok,
        runbook_safe=runbook_safe,
        reason=reason,
    )
