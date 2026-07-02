# OnCall AI

**OnCall AI** is an AI on-call engineer for teams without a dedicated Site Reliability Engineering (SRE) team. 

Built on the **Lemma** platform as a "Pod", OnCall AI actively monitors alerts, triages incidents, investigates root causes, safely applies auto-remediations based on configured runbooks, and generates blameless postmortems—all while keeping your engineering team updated in real-time via Slack or Telegram.

## Powered by Lemma
This project is built using the **Lemma SDK**, a framework for creating autonomous AI agents and workflows. You can learn more about Lemma or contribute to the core platform at the official repository: [https://github.com/lemma-work/lemma-platform](https://github.com/lemma-work/lemma-platform).

---

## Directory Structure

This repository follows a standard Lemma pod architecture. Here is where everything lives:

- **`pod.json`**: The root configuration file defining the pod's identity, version, and environment variables (e.g., Slack/Telegram connectors).
- **`agents/`**: Definitions and prompts for the AI personas powering the pod (`oncall_responder`, `incident_analyst`, `postmortem_writer`).
- **`workflows/`**: Automated step-by-step processes for handling incidents or alerts.
- **`functions/`**: Custom python/node scripts that provide logic (e.g., triage safety gates, executing remediations).
- **`tables/`**: Database schemas and data storage definitions (e.g., `alerts`, `incidents`, `remediation_actions`).
- **`surfaces/`**: Chat interfaces and connector definitions linking the AI to apps like Slack and Telegram.
- **`schedules/`**: Recurring cron jobs for proactive monitoring.
- **`apps/`**: Custom user-facing applications. The UI dashboard is located in `apps/oncall-dashboard/source/`.
- **`files/`**: Static assets, including Markdown runbooks used for auto-remediation checks.
- **`seed/`**: Scripts and payloads for triggering mock alerts during testing and demos.

---

## Component Details

### Agents
- `incident_analyst`: The primary AI detective that analyzes incoming alerts, consults runbooks, and proposes remediations.
- `oncall_responder`: The conversational AI interface that engineering teams chat with on Slack/Telegram.
- `postmortem_writer`: The AI responsible for generating blameless postmortems after an incident is resolved.

### Workflows
- `heal`: A specialized workflow attempting to auto-resolve or run scripts to heal systems.
- `health_check`: Automated checks to ensure system uptime and integrity.
- `incident_response`: The main end-to-end loop that takes a new alert, routes it to the analyst, opens an incident, checks safety gates, and executes remediations or requests human approval.

### Functions
- `dedupe_and_correlate`: Groups new alerts into existing incidents to prevent alert fatigue.
- `execute_remediation`: Safely applies the decided fix (e.g., restarts, scale-ups) based on the runbook.
- `inspect`: Retrieves logs or metrics to aid in debugging.
- `notify`: Routes incident updates and approval requests to the correct chat channels.
- `open_incident`: Applies deterministic safety gates (e.g., severity thresholds, confidence checks) to an AI's proposed fix.
- `probe_service`: Pings or checks a service's immediate status.
- `resolve_approval`: Processes human approval or rejection of an AI's proposed remediation.
- `triage_score`: A scoring function that calculates the severity and auto-remediation eligibility of an issue.

### Tables (Database)
- `alerts`: Raw incoming monitoring events (e.g., from Datadog, Cloudwatch).
- `incidents`: High-level issues that group one or more alerts together.
- `monitored_services`: A registry of all services and their default behaviors.
- `notification_settings`: Routes for alerts, mapping them to specific Slack/Telegram channels based on severity.
- `remediation_actions`: Log of actions proposed and/or taken by the AI.

### Schedules
- `alert_trigger`: Cron job for synthetic alert generation.
- `heal`: Scheduled automated healing checks.
- `health_poll`: Routine polling of monitored endpoints.

### Seed Data
The `seed/` directory provides pre-packaged mock alert payloads (like `automated_req.json` and `human_req.json`) alongside PowerShell scripts to trigger end-to-end testing scenarios instantly.

### Files
The `files/` directory stores static assets. Crucially, `files/runbooks/` contains the markdown runbooks (e.g., `automated-service.md`, `payment-service.md`) that the `incident_analyst` agent reads to decide how to fix an issue and whether auto-remediation is safe.

---

## Development and Testing

- **Lemma Components:** Development involves modifying configuration files (JSON/YAML) and scripts within `agents/`, `workflows/`, `functions/`, and `surfaces/`. These define the AI's behavior and integrations.
- **Dashboard Development:** The UI is located in `apps/oncall-dashboard/source/`. It runs directly from the source. To run it locally, navigate to that directory and execute `npm start`.
- **End-to-End Testing:** Testing the core AI logic requires deploying the pod to a Lemma environment and triggering the relevant workflows or interacting with the configured Slack surface.

---

## Deploying to the Cloud

To push the latest code to your live Lemma cloud pod, you can typically use `lemma pod import .`. 

However, on Windows, importing the entire directory may cause a `[WinError 2]` crash when trying to build the `apps/oncall-dashboard` using `npm ci`. This happens because the Python subprocess driving the CLI fails to execute the Windows `npm.cmd` script without a shell.

**Workaround:** You can bypass the app build step and successfully push all backend components by running the provided PowerShell deployment script from the repository root:

```powershell
.\deploy.ps1
```

If you add new static files (like runbooks), you can sync them explicitly without a full deploy:
```powershell
lemma file upload ./files/runbooks/your-file.md /runbooks/your-file.md
```

---

## Triggering Mock Alerts (Demos & Testing)

To test the workflows or present a demo, you can inject mock data into the `alerts` table. The Lemma CLI communicates directly with your cloud pod, so these local scripts will immediately trigger the live incident workflows in the cloud.

The `seed/` directory contains pre-configured scenarios:

### 1. The Human-in-the-Loop Scenario (Critical)
This scenario simulates a critical database connection pool exhaustion. Because the severity is `critical`, the safety gates will **block auto-remediation** and force the AI to ask a human for approval in Slack/Telegram.

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
