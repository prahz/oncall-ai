#input_type_name: NotifyInput
#output_type_name: NotifyResult
#function_name: notify

from typing import List, Optional
from pydantic import BaseModel, Field
from lemma_sdk import FunctionContext, Pod

# Events that escalate to humans go to the "escalations" target; status updates go to
# the "incidents" target. The per-channel destinations + connector wiring live in the
# notification_settings table (not hardcoded), so this works for slack, telegram, etc.
_ESCALATION_EVENTS = {"needs_approval", "escalated"}


class NotifyInput(BaseModel):
    incident_id: str
    event: str = "resolved"          # needs_approval | escalated | resolved | auto_remediated
    channel: Optional[str] = None    # restrict to a single channel name (default: all enabled)


class ChannelResult(BaseModel):
    channel: str
    posted: bool
    skipped_reason: str = ""
    ref: str = ""


class NotifyResult(BaseModel):
    incident_id: str
    event: str
    delivered: int = 0
    results: List[ChannelResult] = Field(default_factory=list)
    message: str = ""


def _pct(v) -> str:
    try:
        return f"{round(float(v) * 100)}%"
    except (TypeError, ValueError):
        return "—"


def _build_message(event: str, inc: dict) -> str:
    number = inc.get("number")
    title = inc.get("title") or "(untitled incident)"
    service = inc.get("service") or "unknown"
    severity = (inc.get("severity") or "—").upper()
    root_cause = inc.get("root_cause") or "—"
    fix = inc.get("suggested_fix") or "—"
    confidence = _pct(inc.get("confidence"))
    status = inc.get("status") or ""
    header = f"INC-{number} · {title}"

    if event == "needs_approval":
        return (
            f":rotating_light: *Approval needed — {header}*\n"
            f"*Service:* {service}   *Severity:* {severity}   *Confidence:* {confidence}\n"
            f"*Root cause:* {root_cause}\n"
            f"*Proposed fix:* {fix}\n"
            f"_Reply 'approve' or 'reject', or use the Oncall AI dashboard._"
        )
    if event == "escalated":
        return (
            f":warning: *Escalation — {header}*\n"
            f"*Service:* {service}   *Severity:* {severity}\n"
            f"Automated remediation did not pass the health re-check; a human is needed.\n"
            f"*Last proposed fix:* {fix}"
        )
    if event == "auto_remediated":
        return (
            f":white_check_mark: *Auto-remediated — {header}*\n"
            f"*Service:* {service}   *Severity:* {severity}\n"
            f"Runbook-safe fix applied automatically and the health check passed.\n"
            f"*Fix:* {fix}"
        )
    # resolved (default) — reflect the live incident status
    if status == "resolved":
        icon, line = ":white_check_mark:", "Incident resolved; health check passed."
    elif status == "mitigating":
        icon, line = ":warning:", "Fix applied but health check failed — still mitigating, human needed."
    else:
        icon, line = ":information_source:", f"Status: {status or 'updated'}."
    return (
        f"{icon} *{header}*\n"
        f"*Service:* {service}   *Severity:* {severity}\n"
        f"{line}\n"
        f"*Fix:* {fix}"
    )


def _send(pod: Pod, row: dict, event: str, text: str) -> ChannelResult:
    name = row.get("channel") or "?"
    if not row.get("enabled", False):
        return ChannelResult(channel=name, posted=False, skipped_reason="disabled")

    auth_config = row.get("auth_config")
    operation = row.get("send_operation")
    if not auth_config or not operation:
        return ChannelResult(channel=name, posted=False, skipped_reason="not configured")

    # Pick the destination for this event, fall back to incidents target.
    target = row.get("escalations_target") if event in _ESCALATION_EVENTS else row.get("incidents_target")
    target = target or row.get("incidents_target") or row.get("escalations_target")
    if not target:
        return ChannelResult(channel=name, posted=False, skipped_reason="no target")

    target_field = row.get("target_field") or "channel"
    payload = {target_field: target, "text": text}

    kwargs = {}
    if row.get("account_id"):
        kwargs["account_id"] = row["account_id"]

    try:
        resp = pod.connectors.execute(
            auth_config, operation, {"body": payload}, **kwargs
        ).to_dict().get("result", {})
    except Exception as exc:  # a misconfigured channel must not break the others
        return ChannelResult(channel=name, posted=False, skipped_reason=f"error: {exc}"[:160])

    ok = bool(resp.get("ok", True)) if isinstance(resp, dict) else True
    ref = ""
    if isinstance(resp, dict):
        ref = str(resp.get("ts") or resp.get("message_id") or resp.get("channel") or "")
    return ChannelResult(channel=name, posted=ok, ref=ref)


async def notify(ctx: FunctionContext, data: NotifyInput) -> NotifyResult:
    pod = Pod.from_env()
    inc = pod.table("incidents").get(data.incident_id)
    text = _build_message(data.event, inc)

    rows = pod.records.list("notification_settings", limit=50).to_dict()["items"]
    if data.channel:
        rows = [r for r in rows if r.get("channel") == data.channel]

    results = [_send(pod, r, data.event, text) for r in rows]
    delivered = sum(1 for r in results if r.posted)

    return NotifyResult(
        incident_id=data.incident_id,
        event=data.event,
        delivered=delivered,
        results=results,
        message=text,
    )
