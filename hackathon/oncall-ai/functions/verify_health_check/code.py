#input_type_name: HealthCheckInput
#output_type_name: HealthCheckResult
#function_name: verify_health_check

from pydantic import BaseModel
from lemma_sdk import FunctionContext


class HealthCheckInput(BaseModel):
    incident_id: str
    affected_services: list[str] = []


class HealthCheckResult(BaseModel):
    healthy: bool
    services_checked: list[str]
    reason: str


def verify_health_check(ctx: FunctionContext, data: HealthCheckInput) -> HealthCheckResult:
    """STUB — Day 4 will implement real health check polling. For now: deterministic
    by the last character of incident_id so tests are reproducible. Simulate failure
    only for incident ids ending in '9' (escalation-path test)."""
    last_char = str(data.incident_id)[-1] if data.incident_id else ""
    if last_char == "9":
        return HealthCheckResult(
            healthy=False,
            services_checked=data.affected_services,
            reason="STUB: Simulated health check failure for testing escalation path",
        )
    return HealthCheckResult(
        healthy=True,
        services_checked=data.affected_services,
        reason="STUB: Simulated health check success",
    )
