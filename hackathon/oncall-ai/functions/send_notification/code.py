#input_type_name: NotifyInput
#output_type_name: NotifyResult
#function_name: send_notification

from pydantic import BaseModel
from lemma_sdk import FunctionContext, Pod


class NotifyInput(BaseModel):
    template: str
    incident_id: str = ""
    severity: str = ""
    blast_radius: str = ""
    on_call_engineer: str = ""
    remediation_actions: str = ""
    post_mortem_id: str = ""
    incident_title: str = ""
    incident_duration: str = ""
    assigned_reviewer: str = ""
    resolved_at: str = ""
    services_checked: str = ""
    reason: str = ""
    escalate_to: str = ""
    message: str = ""


class NotifyResult(BaseModel):
    notification_id: str
    template: str
    body: str


# Day 4 wires these to the real Slack surface with interactive buttons. Today the
# rendered text is logged to the notifications table.
TEMPLATES = {
    "INCIDENT_ALERT_APPROVAL_REQUIRED":
        "🚨 INCIDENT DETECTED — APPROVAL REQUIRED\nIncident: {incident_id}\nSeverity: {severity}\n"
        "Blast Radius: {blast_radius}\nOn-Call: {on_call_engineer}\nProposed Remediation: {remediation_actions}\n"
        "⚠️ Human approval required before any action is taken.",
    "INCIDENT_ALERT_AUTO_REMEDIATION":
        "🚨 INCIDENT DETECTED — AUTO-REMEDIATION ELIGIBLE\nIncident: {incident_id}\nSeverity: {severity}\n"
        "Blast Radius: {blast_radius}\nOn-Call: {on_call_engineer}\nProposed Remediation: {remediation_actions}\n"
        "✅ Confidence and runbook safety checks passed — awaiting approval to auto-execute.",
    "INCIDENT_RESOLVED":
        "✅ INCIDENT RESOLVED\nIncident: {incident_id}\nResolved At: {resolved_at}\n{message}",
    "REMEDIATION_FAILED":
        "❌ REMEDIATION FAILED — HUMAN REQUIRED\nIncident: {incident_id}\nReason: {reason}\n{message}",
    "ESCALATION_ALERT":
        "🔴 ESCALATION REQUIRED\nIncident: {incident_id}\nEscalating To: {escalate_to}\nReason: {reason}",
    "POST_MORTEM_REVIEW_REQUEST":
        "📋 POST-MORTEM READY FOR REVIEW\nIncident: {incident_id} — {incident_title}\n"
        "Duration: {incident_duration}\nPost-Mortem ID: {post_mortem_id}\nAssigned To: {assigned_reviewer}\n{message}",
    "POST_MORTEM_EDITS_REQUESTED":
        "✏️ POST-MORTEM EDITS REQUESTED\nPost-Mortem: {post_mortem_id}\n{message}",
    "POST_MORTEM_PUBLISHED":
        "📗 POST-MORTEM PUBLISHED\nPost-Mortem: {post_mortem_id}\nIncident: {incident_id}\n{message}",
    "SYSTEM_LOG":
        "ℹ️ SYSTEM LOG\n{message}",
}


def send_notification(ctx: FunctionContext, data: NotifyInput) -> NotifyResult:
    """STUB — Day 4 sends real Slack. Today: render the named template and log it."""
    fields = data.model_dump()
    template = TEMPLATES.get(data.template, "ℹ️ {message}")
    try:
        body = template.format(**fields)
    except (KeyError, IndexError):
        body = template
    pod = Pod.from_env()
    row = pod.table("notifications").create({
        "template": data.template,
        "channel": "slack",
        "incident_id": data.incident_id or None,
        "body": body,
        "payload": fields,
    })
    return NotifyResult(notification_id=str(row["id"]), template=data.template, body=body)
