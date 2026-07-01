#input_type_name: ProbeInput
#output_type_name: ProbeResult
#function_name: probe_service

from datetime import datetime, timezone
from typing import List, Optional
from pydantic import BaseModel, Field
from lemma_sdk import FunctionContext, Pod
import requests

# How a measured breach maps to an alert. The analyst then reads /runbooks/<service>.md.
HEALTHY_STATUSES = {"healthy", "ok", "up"}


class ProbeInput(BaseModel):
    service: Optional[str] = None      # probe one service by name; default = all enabled


class ServiceProbe(BaseModel):
    service: str
    status: str                        # healthy | degraded | down | unreachable
    alerted: bool = False
    reason: str = ""


class ProbeResult(BaseModel):
    checked: int = 0
    alerts_opened: int = 0
    probes: List[ServiceProbe] = Field(default_factory=list)


def _open_incident_exists(pod: Pod, service: str) -> bool:
    """Don't spam alerts while an incident for this service is already open."""
    open_inc = pod.records.list(
        "incidents", limit=5,
        filter=[
            {"field": "service", "op": "eq", "value": service},
            {"field": "status", "op": "ne", "value": "resolved"},
        ],
    ).to_dict()["items"]
    return bool(open_inc)


def _fire_alert(pod: Pod, service: str, severity: str, metric: str,
                current: float, threshold: float, message: str) -> None:
    pod.table("alerts").create({
        "service": service,
        "source": "healthcheck",
        "severity": severity,
        "metric": metric,
        "current_value": current,
        "threshold": threshold,
        "message": message,
        "status": "new",
    })


def _probe_one(pod: Pod, row: dict) -> ServiceProbe:
    service = row.get("service") or "unknown"
    base = (row.get("base_url") or "").rstrip("/")
    health_path = row.get("health_path") or "/health"
    lat_thr = float(row.get("latency_threshold_ms") or 1000)
    mem_thr = float(row.get("memory_threshold_pct") or 80)
    url = base + health_path

    status = "healthy"
    detail = ""
    severity = None
    metric = None
    current = 0.0
    threshold = 0.0
    message = ""

    try:
        resp = requests.get(url, timeout=15, headers={"ngrok-skip-browser-warning": "1"})
        if resp.status_code >= 500:
            status, severity = "down", "critical"
            metric, current, threshold = "http_status", float(resp.status_code), 500.0
            message = f"{service} health check returned HTTP {resp.status_code} (service down)"
            detail = message
        else:
            body = {}
            try:
                body = resp.json()
            except Exception:
                body = {}
            latency = float(body.get("latency_ms") or 0)
            memory = float(body.get("memory_pct") or 0)
            detail = f"latency={latency:.0f}ms memory={memory:.0f}%"

            if latency > lat_thr:
                status, severity = "degraded", "high"
                metric, current, threshold = "latency_ms", latency, lat_thr
                message = f"{service} p95 latency {latency:.0f}ms over {lat_thr:.0f}ms threshold"
            elif memory > mem_thr:
                status, severity = "degraded", "medium"
                metric, current, threshold = "memory_pct", memory, mem_thr
                message = f"{service} memory at {memory:.0f}% over {mem_thr:.0f}% threshold"
            # Note: we deliberately do NOT alert on a generic reported "status" field.
            # Each monitored row watches its own metric via thresholds (latency/memory);
            # a hard-down is caught by the HTTP 500 branch above. This keeps two rows
            # pointed at one service from both firing on the other's fault.
    except requests.exceptions.Timeout:
        status, severity = "down", "high"
        metric, current, threshold = "latency_ms", lat_thr * 10, lat_thr
        message = f"{service} health check timed out (no response in 15s)"
        detail = message
    except Exception as exc:
        status, severity = "unreachable", None  # unreachable != a service fault we alert on
        detail = f"probe error: {exc}"[:160]

    # Always record the live status for the dashboard.
    pod.table("monitored_services").update(row["id"], {
        "last_status": status,
        "last_checked_at": datetime.now(timezone.utc).isoformat(),
        "last_detail": detail or status,
    })

    # Open an alert only on a real, alertable fault, and only if no incident is open.
    if severity and status in ("degraded", "down"):
        if _open_incident_exists(pod, service):
            return ServiceProbe(service=service, status=status, alerted=False,
                                reason="incident already open; not re-alerting")
        _fire_alert(pod, service, severity, metric, current, threshold, message)
        return ServiceProbe(service=service, status=status, alerted=True, reason=message)

    return ServiceProbe(service=service, status=status, alerted=False, reason=detail or "healthy")


async def probe_service(ctx: FunctionContext, data: ProbeInput) -> ProbeResult:
    pod = Pod.from_env()
    rows = pod.records.list("monitored_services", limit=100).to_dict()["items"]
    rows = [r for r in rows if r.get("enabled", False)]
    if data.service:
        rows = [r for r in rows if r.get("service") == data.service]

    probes = [_probe_one(pod, r) for r in rows]
    return ProbeResult(
        checked=len(probes),
        alerts_opened=sum(1 for p in probes if p.alerted),
        probes=probes,
    )
