#input_type_name: ConfidenceInput
#output_type_name: ConfidenceResult
#function_name: confidence_threshold

from pydantic import BaseModel
from lemma_sdk import FunctionContext


class ConfidenceInput(BaseModel):
    confidence: float
    runbook_safety: bool
    incident_severity: str


class ConfidenceResult(BaseModel):
    auto_approve: bool
    reason: str


def confidence_threshold(ctx: FunctionContext, data: ConfidenceInput) -> ConfidenceResult:
    """STUB — Day 4 will add context checks. Core logic is final and does not change."""
    if data.incident_severity == "critical":
        return ConfidenceResult(
            auto_approve=False,
            reason="Critical incidents always require human approval regardless of confidence",
        )
    if data.confidence >= 0.9 and data.runbook_safety is True:
        return ConfidenceResult(
            auto_approve=True,
            reason=f"Confidence {data.confidence} >= 0.9 and runbook is marked safe",
        )
    return ConfidenceResult(
        auto_approve=False,
        reason=f"Confidence {data.confidence} below 0.9 threshold or runbook not marked safe (safe={data.runbook_safety})",
    )
