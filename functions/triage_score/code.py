#input_type_name: TriageInput
#output_type_name: TriageResult
#config_type_name: TriageConfig
#function_name: triage_score

# Standalone, explainable triage scorer. This mirrors the deterministic logic in
# open_incident so the score can be computed / demoed on its own. It is a pure
# function of its inputs: every point in `score` is explained in `breakdown`.

from datetime import datetime, timezone
from typing import List
from pydantic import BaseModel, Field
from lemma_sdk import FunctionContext

ORDER = ["low", "medium", "high", "critical"]
RANK = {name: i for i, name in enumerate(ORDER)}


class TriageInput(BaseModel):
    severity: str                       # raw severity: critical | high | medium | low
    blast_radius: str = "single_service"
    confidence: float = 0.5             # 0-1 confidence in the suggested fix
    runbook_safe: bool = False          # did a matched runbook say auto-remediation is safe?
    hour_of_day: int = -1               # -1 => use current UTC hour


class TriageConfig(BaseModel):
    min_confidence: float = 0.85        # min confidence to auto-approve


class TriageResult(BaseModel):
    score: int
    final_severity: str
    auto_approve_eligible: bool
    reason: str
    breakdown: List[str] = Field(default_factory=list)


def triage_score(ctx: FunctionContext, data: TriageInput) -> TriageResult:
    breakdown: List[str] = []

    sev_pts = {"critical": 50, "high": 30, "medium": 15, "low": 5}
    s = sev_pts.get(data.severity, 15)
    breakdown.append(f"severity {data.severity} = +{s}")
    score = s

    blast_pts = {"single_service": 0, "multi_service": 15, "infrastructure": 30}
    b = blast_pts.get(data.blast_radius, 0)
    if b:
        breakdown.append(f"blast radius {data.blast_radius} = +{b}")
    score += b

    hour = data.hour_of_day if data.hour_of_day >= 0 else datetime.now(timezone.utc).hour
    if 0 <= hour <= 6:
        breakdown.append("off-hours (00:00-06:00 UTC) = +10")
        score += 10

    if data.confidence < 0.6:
        breakdown.append(f"low confidence ({data.confidence:.0%}) adds risk = +10")
        score += 10

    score = max(0, min(100, score))

    band = ("critical" if score >= 70 else "high" if score >= 45
            else "medium" if score >= 25 else "low")
    final = ORDER[max(RANK.get(data.severity, 1), RANK[band])]
    breakdown.append(f"score {score}/100 -> band {band}; final = "
                     f"max({data.severity}, {band}) = {final}")

    cfg = ctx.config
    min_conf = cfg.min_confidence if cfg else 0.85

    gates = {
        "runbook auto-safe": data.runbook_safe,
        f"confidence >= {min_conf:.0%}": data.confidence >= min_conf,
        "not critical": final != "critical",
        "blast radius not infrastructure": data.blast_radius != "infrastructure",
    }
    auto_ok = all(gates.values())
    failed = [k for k, v in gates.items() if not v]
    reason = ("Auto-approve eligible — all gates passed"
              if auto_ok else "Needs human approval — failed: " + "; ".join(failed))

    return TriageResult(score=score, final_severity=final,
                        auto_approve_eligible=auto_ok, reason=reason,
                        breakdown=breakdown)
