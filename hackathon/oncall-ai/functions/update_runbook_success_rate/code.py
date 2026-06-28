#input_type_name: RunbookRateInput
#output_type_name: RunbookRateResult
#function_name: update_runbook_success_rate

from pydantic import BaseModel
from lemma_sdk import FunctionContext


class RunbookRateInput(BaseModel):
    incident_id: str
    matched_runbook_id: str = ""
    was_successful: bool = True


class RunbookRateResult(BaseModel):
    updated: bool
    matched_runbook_id: str | None = None
    new_success_rate: float | None = None
    reason: str


def update_runbook_success_rate(ctx: FunctionContext, data: RunbookRateInput) -> RunbookRateResult:
    """STUB — Day 6 learning loop will implement the real rolling average. For now:
    return the existing success_rate unchanged."""
    if not data.matched_runbook_id:
        return RunbookRateResult(updated=False, reason="No matched runbook for this incident")
    return RunbookRateResult(
        updated=False,
        matched_runbook_id=data.matched_runbook_id,
        new_success_rate=None,
        reason="STUB: success rate update deferred to Day 6 learning loop",
    )
