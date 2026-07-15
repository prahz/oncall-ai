#input_type_name: HealInput
#output_type_name: HealResult
#function_name: heal

# Scheduled self-healing safety net.
#
# When auto-remediation applies a fix but the health re-check does NOT recover,
# execute_remediation leaves the incident in `mitigating`. This function is the
# retry loop for exactly those incidents: it re-reads the service runbook and,
# only if the runbook still marks the service auto-safe, re-applies the fix a
# bounded number of times. On recovery it resolves; when it exhausts its
# attempts (or the runbook is not auto-safe), it escalates to a human. Runbook
# says human-only -> we never keep retrying, we page.

from typing import List
from pydantic import BaseModel, Field
from lemma_sdk import FunctionContext, Pod

MAX_ATTEMPTS = 3


class HealInput(BaseModel):
    incident_id: str = ""   # optional: heal one incident; default = all mitigating


class HealedIncident(BaseModel):
    incident_id: str
    incident_number: int
    service: str
    outcome: str            # resolved | retrying | escalated | skipped
    attempts: int
    detail: str = ""


class HealResult(BaseModel):
    scanned: int = 0
    resolved: int = 0
    escalated: int = 0
    still_mitigating: int = 0
    incidents: List[HealedIncident] = Field(default_factory=list)


def _runbook_safe(pod: Pod, service: str) -> bool:
    try:
        rows = pod.records.list(
            "runbooks", limit=1,
            filter=[{"field": "service", "op": "eq", "value": service}],
        ).to_dict()["items"]
    except Exception:
        return False
    return bool(rows and rows[0].get("auto_safe"))


def _latest_action(pod: Pod, incident_id: str):
    rows = pod.records.list(
        "remediation_actions", limit=20,
        filter=[{"field": "incident_id", "op": "eq", "value": incident_id}],
        sort=[{"field": "created_at", "direction": "desc"}],
    ).to_dict()["items"]
    return rows[0] if rows else None


async def heal(ctx: FunctionContext, data: HealInput) -> HealResult:
    pod = Pod.from_env()
    inc_tbl = pod.table("incidents")

    if data.incident_id:
        stuck = [inc_tbl.get(data.incident_id)]
    else:
        stuck = pod.records.list(
            "incidents", limit=25,
            filter=[{"field": "status", "op": "eq", "value": "mitigating"}],
            sort=[{"field": "created_at", "direction": "asc"}],
        ).to_dict()["items"]

    result = HealResult(scanned=len(stuck))

    for inc in stuck:
        incident_id = str(inc["id"])
        number = int(inc.get("number") or 0)
        service = inc.get("service") or "unknown"
        attempts = int(inc.get("heal_attempts") or 0)

        action = _latest_action(pod, incident_id)
        if not action:
            result.incidents.append(HealedIncident(
                incident_id=incident_id, incident_number=number, service=service,
                outcome="skipped", attempts=attempts, detail="no remediation action to retry"))
            continue

        # Runbook is the source of truth. If it isn't auto-safe, don't loop — page a human.
        if not _runbook_safe(pod, service):
            if attempts < MAX_ATTEMPTS:
                inc_tbl.update(incident_id, {"heal_attempts": MAX_ATTEMPTS})
                pod.functions.run("notify", {"incident_id": incident_id, "event": "escalated"})
            result.escalated += 1
            result.incidents.append(HealedIncident(
                incident_id=incident_id, incident_number=number, service=service,
                outcome="escalated", attempts=attempts,
                detail="runbook not auto-safe — escalated to human"))
            continue

        if attempts >= MAX_ATTEMPTS:
            result.still_mitigating += 1
            result.incidents.append(HealedIncident(
                incident_id=incident_id, incident_number=number, service=service,
                outcome="escalated", attempts=attempts,
                detail=f"exhausted {MAX_ATTEMPTS} auto-retries — awaiting human"))
            continue

        # Re-apply the runbook fix by reusing execute_remediation (real health
        # re-check if the service is monitored, simulated otherwise).
        attempts += 1
        inc_tbl.update(incident_id, {"heal_attempts": attempts})
        try:
            pod.functions.run("execute_remediation", {
                "remediation_action_id": str(action["id"]),
                "simulate_healthy": True,
            })
        except Exception as exc:
            result.incidents.append(HealedIncident(
                incident_id=incident_id, incident_number=number, service=service,
                outcome="retrying", attempts=attempts, detail=f"retry error: {exc}"[:160]))
            continue

        refreshed = inc_tbl.get(incident_id)
        if refreshed.get("status") == "resolved":
            pod.functions.run("notify", {"incident_id": incident_id, "event": "resolved"})
            result.resolved += 1
            result.incidents.append(HealedIncident(
                incident_id=incident_id, incident_number=number, service=service,
                outcome="resolved", attempts=attempts,
                detail=f"self-healed on retry {attempts}"))
        elif attempts >= MAX_ATTEMPTS:
            pod.functions.run("notify", {"incident_id": incident_id, "event": "escalated"})
            result.escalated += 1
            result.incidents.append(HealedIncident(
                incident_id=incident_id, incident_number=number, service=service,
                outcome="escalated", attempts=attempts,
                detail=f"still failing after {attempts} retries — escalated"))
        else:
            result.still_mitigating += 1
            result.incidents.append(HealedIncident(
                incident_id=incident_id, incident_number=number, service=service,
                outcome="retrying", attempts=attempts,
                detail=f"retry {attempts} did not recover; will retry next cycle"))

    return result
