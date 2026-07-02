# OnCall AI

**OnCall AI** is an AI on-call engineer for teams without a dedicated Site Reliability Engineering (SRE) team. 

Built on the **Lemma** platform as a "Pod", OnCall AI actively monitors alerts, triages incidents, investigates root causes, safely applies auto-remediations based on configured runbooks, and generates blameless postmortems—all while keeping your engineering team updated in real-time via Slack or Telegram.

## Directory Structure

This repository contains the full definition of the OnCall AI Pod:

- **`pod.json`**: The core configuration file for the pod and its environment variables (e.g., Slack/Telegram connectors).
- **`agents/`**: The AI personas powering the pod (`oncall_responder`, `incident_analyst`, `postmortem_writer`).
- **`workflows/`**: The automated flows that dictate how alerts turn into incidents and remediations.
- **`functions/`**: Custom python/node scripts that provide logic (e.g., triage safety gates, executing remediations).
- **`tables/`**: Database schemas (e.g., `alerts`, `incidents`, `remediation_actions`).
- **`surfaces/`**: Connector definitions linking the AI to chat apps like Slack and Telegram.
- **`schedules/`**: Recurring jobs for proactive monitoring.
- **`apps/`**: Custom user-facing dashboards.
- **`files/`**: Static assets, including Markdown runbooks used for auto-remediation checks.
- **`seed/`**: Scripts and payloads for triggering mock alerts during testing and demos.

---

## Deploying to the Cloud

To push the latest code to your live Lemma cloud pod, you can typically use `lemma pod import .`. 

However, on Windows, importing the entire directory may cause a `[WinError 2]` crash when trying to build the `apps/oncall-dashboard` using `npm ci`. 

**Workaround:** You can bypass the app build step and successfully push all backend components by running this script in your PowerShell terminal from the repository root:

```powershell
.\deploy.ps1
```

If you add new static files (like runbooks), sync them explicitly:
```powershell
lemma file upload ./files/runbooks/your-file.md /runbooks/your-file.md
```

---

## Triggering Mock Alerts (Demos & Testing)

To test the workflows or present a demo, you can inject mock data into the `alerts` table. The Lemma CLI communicates directly with your cloud pod, so these local scripts will immediately trigger the live incident workflows in the cloud.

The `seed/` directory contains two pre-configured scenarios:

### 1. The Human-in-the-Loop Scenario (Critical)
This scenario simulates a critical database connection pool exhaustion. Because the severity is `critical`, the `open_incident` safety gates will **block auto-remediation** and force the AI to ask a human for approval in Slack/Telegram.

**Trigger it:**
```powershell
cd seed\
.\trigger_human.ps1
```

### 2. The Auto-Remediation Scenario (Safe)
This scenario simulates a medium-severity incident on `automated-service`. Because a runbook exists for this service (`files/runbooks/automated-service.md`) that explicitly says `"Auto-remediation safe: yes"`, the AI will **automatically execute the fix** without human intervention.

**Trigger it:**
```powershell
cd seed\
.\trigger_automated.ps1
```

### Custom Alerts
You can easily create new mock alerts by making a new `.json` file in the `seed/` directory:

```json
{
  "service": "my-custom-service",
  "source": "datadog",
  "severity": "high",
  "message": "Custom error description."
}
```
Then deploy it via:
```powershell
lemma record create alerts --file my_custom_alert.json
```
