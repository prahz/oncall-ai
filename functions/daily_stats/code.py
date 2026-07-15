#input_type_name: StatsInput
#output_type_name: StatsResult
#function_name: daily_stats

# Posts an incident-ops digest to Slack/Telegram. Wired to a daily cron schedule
# and also callable on demand. Honors alert_rules (event=daily_stats) per channel.

from typing import List
from pydantic import BaseModel, Field
from lemma_sdk import FunctionContext, Pod


class StatsInput(BaseModel):
    channel: str = ""     # optional: restrict to one channel name


class StatsResult(BaseModel):
    delivered: int = 0
    message: str = ""


def _all(pod: Pod, table: str):
    return pod.records.list(table, limit=500).to_dict()["items"]


async def daily_stats(ctx: FunctionContext, data: StatsInput) -> StatsResult:
    pod = Pod.from_env()
    incs = _all(pod, "incidents")
    total = len(incs)
    resolved = sum(1 for i in incs if i.get("status") == "resolved")
    active = sum(1 for i in incs if i.get("status") in ("detected", "triaging", "mitigating"))
    ra = _all(pod, "remediation_actions")
    auto = sum(1 for a in ra if a.get("auto_approved") and a.get("status") == "executed")
    pending = sum(1 for a in ra if a.get("status") == "pending_approval")
    try:
        delg = _all(pod, "delegations")
        pushed = sum(1 for d in delg if d.get("status") == "pushed")
        working = sum(1 for d in delg if d.get("status") in ("queued", "working"))
    except Exception:
        pushed = working = 0

    msg = (
        ":bar_chart: *oncall — daily incident digest*\n"
        f"*Incidents:* {total} total · {active} active · {resolved} resolved\n"
        f"*Auto-remediated:* {auto}   *Awaiting approval:* {pending}\n"
        f"*Delegations:* {working} in progress · {pushed} pushed to repo"
    )

    rules = _all(pod, "alert_rules")
    ns = _all(pod, "notification_settings")
    delivered = 0
    for row in ns:
        ch = row.get("channel")
        if data.channel and ch != data.channel:
            continue
        if not row.get("enabled"):
            continue
        chrules = [r for r in rules if r.get("channel") == ch and r.get("event") == "daily_stats"]
        if chrules and not any(r.get("enabled") for r in chrules):
            continue
        auth, op = row.get("auth_config"), row.get("send_operation")
        target = row.get("incidents_target") or row.get("escalations_target")
        if not (auth and op and target):
            continue
        payload = {row.get("target_field") or "channel": target, "text": msg}
        kwargs = {}
        if row.get("account_id"):
            kwargs["account_id"] = row["account_id"]
        try:
            pod.connectors.execute(auth, op, {"body": payload}, **kwargs)
            delivered += 1
        except Exception:
            pass

    return StatsResult(delivered=delivered, message=msg)
