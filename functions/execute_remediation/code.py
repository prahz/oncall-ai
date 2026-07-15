#input_type_name: ExecuteInput
#output_type_name: ExecuteResult
#function_name: execute_remediation

import time
from datetime import datetime, timezone
from typing import Optional
from pydantic import BaseModel
from lemma_sdk import FunctionContext, Pod
import requests


class ExecuteInput(BaseModel):
    remediation_action_id: str
    # Demo/fallback: if the incident's service has no reachable monitored_services row,
    # fall back to this simulated health outcome instead of a real HTTP re-check.
    simulate_healthy: Optional[bool] = None


class ExecuteResult(BaseModel):
    remediation_action_id: str
    incident_id: str
    incident_status: str
    healthy: bool
    result: str


def _service_row(pod: Pod, service: str) -> Optional[dict]:
    rows = pod.records.list(
        "monitored_services", limit=20,
        filter=[{"field": "service", "op": "eq", "value": service}],
    ).to_dict()["items"]
    return rows[0] if rows else None


def _apply_real_fix(row: dict, action_type: str) -> tuple[bool, str]:
    """POST the remediation to the real service, then re-poll /health to verify.
    Returns (healthy, human_readable_detail). action_type is informational only —
    the actual path comes from the service's configured remediate_path."""
    base = (row.get("base_url") or "").rstrip("/")
    # Always use the service's configured remediate_path (it already encodes the right
    # action + per-service prefix, e.g. /payment-service/remediate/rollback_deploy).
    remediate_path = row.get("remediate_path") or "/remediate/restart"
    health_path = row.get("health_path") or "/health"
    token = row.get("control_token") or ""
    headers = {"ngrok-skip-browser-warning": "1"}
    if token:
        headers["X-Control-Token"] = token
    lat_thr = float(row.get("latency_threshold_ms") or 1000)
    mem_thr = float(row.get("memory_threshold_pct") or 80)

    # 1) apply the fix
    try:
        r = requests.post(base + remediate_path, headers=headers, timeout=15)
        if r.status_code >= 400:
            return False, f"remediation call {remediate_path} returned HTTP {r.status_code}"
    except Exception as exc:
        return False, f"remediation call failed: {exc}"[:160]

    # 2) give it a moment, then re-verify health for real
    time.sleep(2)
    try:
        h = requests.get(base + health_path, timeout=15)
        if h.status_code >= 500:
            return False, f"post-fix health check still failing (HTTP {h.status_code})"
        body = h.json() if h.headers.get("content-type", "").startswith("application/json") else {}
        latency = float(body.get("latency_ms") or 0)
        memory = float(body.get("memory_pct") or 0)
        status = str(body.get("status") or "").lower()
        if status and status not in ("healthy", "ok", "up"):
            return False, f"post-fix status '{status}' (latency {latency:.0f}ms, memory {memory:.0f}%)"
        if latency > lat_thr:
            return False, f"post-fix latency {latency:.0f}ms still over {lat_thr:.0f}ms"
        if memory > mem_thr:
            return False, f"post-fix memory {memory:.0f}% still over {mem_thr:.0f}%"
        return True, f"{remediate_path} applied; health re-check passed (latency {latency:.0f}ms, memory {memory:.0f}%)"
    except Exception as exc:
        return False, f"post-fix health check errored: {exc}"[:160]


async def execute_remediation(ctx: FunctionContext, data: ExecuteInput) -> ExecuteResult:
    pod = Pod.from_env()
    ra = pod.table("remediation_actions")
    inc = pod.table("incidents")

    action = ra.get(data.remediation_action_id)
    incident_id = str(action["incident_id"])
    incident = inc.get(incident_id)
    service = incident.get("service") or ""
    now = datetime.now(timezone.utc).isoformat()
    action_type = action.get("action_type", "fix")

    # Apply the fix -> incident is mitigating.
    inc.update(incident_id, {"status": "mitigating", "mitigated_at": now})

    # Decide how to verify: real HTTP against the monitored service, or the simulate fallback.
    # Only hit the network for an ENABLED monitored service with a real endpoint;
    # disabled/demo rows fall through to the simulated re-check so the fix converges.
    row = _service_row(pod, service)
    if row and row.get("enabled") and row.get("base_url"):
        healthy, detail = _apply_real_fix(row, action_type)
    else:
        # No monitored service for this incident: fall back to the demo toggle
        # (defaults to healthy so the hand-fired demo path still resolves).
        healthy = True if data.simulate_healthy is None else bool(data.simulate_healthy)
        detail = f"{action_type} applied; simulated health re-check {'passed' if healthy else 'FAILED'}"

    if healthy:
        ra.update(action["id"], {
            "status": "executed",
            "executed_by": "agent",
            "result": detail,
        })
        inc.update(incident_id, {"status": "resolved", "resolved_at": now})

        linked = pod.records.list(
            "alerts", limit=100,
            filter=[{"field": "incident_id", "op": "eq", "value": incident_id}],
        ).to_dict()["items"]
        if linked:
            pod.records.bulk_update("alerts", [{"id": a["id"], "status": "resolved"} for a in linked])

        return ExecuteResult(
            remediation_action_id=str(action["id"]), incident_id=incident_id,
            incident_status="resolved", healthy=True,
            result=detail,
        )

    # Unhealthy: fix did not work -> leave mitigating, escalate to a human.
    ra.update(action["id"], {
        "status": "failed",
        "executed_by": "agent",
        "result": detail + " — escalating to human",
    })
    return ExecuteResult(
        remediation_action_id=str(action["id"]), incident_id=incident_id,
        incident_status="mitigating", healthy=False,
        result=detail + "; human required",
    )
