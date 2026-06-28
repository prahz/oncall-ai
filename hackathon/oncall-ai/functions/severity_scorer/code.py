#input_type_name: SeverityInput
#output_type_name: SeverityResult
#function_name: severity_scorer

from pydantic import BaseModel
from lemma_sdk import FunctionContext


class SeverityInput(BaseModel):
    alert_severity: str
    blast_radius: str
    affected_users: int = 0
    time_of_day: str | None = None


class SeverityResult(BaseModel):
    severity: str
    original_severity: str
    adjusted: bool
    reason: str


def severity_scorer(ctx: FunctionContext, data: SeverityInput) -> SeverityResult:
    """STUB — Day 4 will implement the full scoring matrix with time-of-day logic.
    For now: promote severity one level if blast_radius is multi_service, two if
    infrastructure."""
    order = ["low", "medium", "high", "critical"]
    base = data.alert_severity if data.alert_severity in order else "medium"
    idx = order.index(base)

    if data.blast_radius == "infrastructure" and idx < 3:
        idx += 2
    elif data.blast_radius == "multi_service" and idx < 3:
        idx += 1

    final = order[min(idx, 3)]
    adjusted = final != data.alert_severity
    return SeverityResult(
        severity=final,
        original_severity=data.alert_severity,
        adjusted=adjusted,
        reason=(f"Blast radius '{data.blast_radius}' triggered severity upgrade"
                if adjusted else "No adjustment needed"),
    )
