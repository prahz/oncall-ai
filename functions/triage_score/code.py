#input_type_name: TriageInput
#output_type_name: TriageResult
#config_type_name: TriageConfig
#function_name: triage_score

from datetime import datetime, timezone
from pydantic import BaseModel
from lemma_sdk import FunctionContext


class TriageInput(BaseModel):
    severity: str                       # raw severity: critical | high | medium | low
    blast_radius: str = "single_service"
    confidence: float = 0.0             # 0-1 confidence in the suggested fix
    runbook_safe: bool = False          # did a matched runbook say auto-remediation is safe?
    affected_users: int = 0
    hour_of_day: int = -1               # -1 => use current UTC hour
    min_confidence: float = -1.0        # optional per-call override of the autonomy dial


class TriageConfig(BaseModel):
    min_confidence: float = 0.9         # default auto-approve confidence threshold
    auto_max_severity: str = "high"     # never auto-approve above this severity


class TriageResult(BaseModel):
    score: int
    final_severity: str
    auto_approve_eligible: bool
    reason: str


def triage_score(ctx: FunctionContext, data: TriageInput) -> TriageResult:
    base = {"critical": 40, "high": 25, "medium": 10, "low": 0}
    radius = {"single_service": 10, "multi_service": 25, "infrastructure": 40}
    score = base.get(data.severity, 0) + radius.get(data.blast_radius, 0)

    hour = data.hour_of_day if data.hour_of_day >= 0 else datetime.now(timezone.utc).hour
    if 0 <= hour <= 6:
        score += 15                     # 3am incidents are worse: fewer humans awake

    if data.affected_users > 10000:
        score += 20
    elif data.affected_users > 1000:
        score += 10

    order = ["low", "medium", "high", "critical"]
    rank = {name: i for i, name in enumerate(order)}

    if score >= 70:
        score_sev = "critical"
    elif score >= 45:
        score_sev = "high"
    elif score >= 20:
        score_sev = "medium"
    else:
        score_sev = "low"

    # Scoring only ESCALATES — never downgrade the raw severity (a critical stays critical).
    raw = data.severity if data.severity in rank else "low"
    final = order[max(rank[raw], rank[score_sev])]

    cfg = ctx.config
    min_conf = data.min_confidence if data.min_confidence >= 0 else (cfg.min_confidence if cfg else 0.9)
    auto_max = cfg.auto_max_severity if cfg else "high"

    auto_ok = (
        final != "critical"
        and rank.get(final, 3) <= rank.get(auto_max, 2)
        and data.confidence >= min_conf
        and data.runbook_safe
    )

    if final == "critical":
        reason = "Critical incidents always require human approval"
    elif not data.runbook_safe:
        reason = "No runbook marked auto-remediation safe"
    elif data.confidence < min_conf:
        reason = f"Confidence {data.confidence:.2f} below threshold {min_conf:.2f}"
    elif auto_ok:
        reason = "High confidence + safe runbook + non-critical: auto-approve eligible"
    else:
        reason = "Does not meet auto-approval rules"

    return TriageResult(score=score, final_severity=final, auto_approve_eligible=auto_ok, reason=reason)
