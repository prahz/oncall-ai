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

### Runbooks (the AI's knowledge base)
Runbooks live in the **`runbooks` table** (one row per service: `service`, `title`,
`tier`, `auto_safe`, `content`). The `incident_analyst` reads a service's runbook to
diagnose and propose a fix; `open_incident` and `heal` read the deterministic
`auto_safe` flag to decide whether the AI may act without a human. The markdown
source lives in `files/runbooks/*.md` and is loaded into the table by the `_bootstrap`
function (run `python scripts/build_bootstrap.py` after editing a runbook, then
re-deploy). After an incident, `postmortem_writer` **appends a dated lesson** to the
runbook row — the runbooks improve themselves over time.

> Why a table and not `/files`? The hosted file API rejects writes from the current
> CLI/runtime, so all docs (runbooks **and** post-mortems) are stored in tables, which
> are reliably writable from every layer.

---

## Development and Testing

- **Lemma Components:** Development involves modifying configuration files (JSON/YAML) and scripts within `agents/`, `workflows/`, `functions/`, and `surfaces/`. These define the AI's behavior and integrations.
- **Dashboard Development:** The UI is located in `apps/oncall-dashboard/source/`. It runs directly from the source. To run it locally, navigate to that directory and execute `npm start`.
- **End-to-End Testing:** Testing the core AI logic requires deploying the pod to a Lemma environment and triggering the relevant workflows or interacting with the configured Slack surface.

---

## Deploying to the Cloud

The live pod is **`Oncall-AI`** (`019f1e93-…`) in the `harshdumpss-s-space` org — the
one that serves the dashboard at `oncall-dashboard-harsh-dev.apps.lemma.work`. There
are several look-alike pods on this account, so **always deploy with the pinned
script**, which targets that pod explicitly:

```powershell
.\deploy.ps1
```

`deploy.ps1` imports every backend resource, runs the `_bootstrap` function (seeds the
`runbooks` and `monitored_services` tables), and deploys the dashboard app — pinning
`--org`/`--pod` on every call and working around the Windows `[WinError 2]` npm-build
crash.

If you edit a runbook under `files/runbooks/`, re-embed it and re-deploy:
```powershell
python scripts/build_bootstrap.py    # refresh the embedded runbooks
.\deploy.ps1                         # re-import + re-run _bootstrap
```

---

## Running a Demo

Everything is driven from the **dashboard** (`oncall-dashboard-harsh-dev.apps.lemma.work`)
— no terminal needed. The dashboard runs each scenario's full lifecycle directly on the
datastore (reading the real `runbooks` table and computing the real triage score), so it
is **instant and reliable** for a live demo — it does not wait on the serverless
functions, whose cold-starts on this pod tier are slow.

1. **Auto-remediation story.** Simulate **"GC thrashing / high latency"** (api-gateway)
   or **"Service unresponsive"** (automated-service). The runbook marks these auto-safe,
   so the incident triages, executes the fix, resolves, and writes a post-mortem —
   hands-free, live in front of you. Open the incident to show the **triage-score
   breakdown**, the **timeline**, and the **post-mortem** (📄).
2. **Human-in-the-loop story.** Simulate **"DB connection pool exhausted"** (critical) or
   **"Payment errors after deploy"**. The runbook is *not* auto-safe, so it lands in the
   **Approval queue**. Click **Approve** and watch it execute and resolve (or **Reject**
   to escalate).
3. **Self-healing story.** Simulate **"a stuck incident"** (it lands in `mitigating`),
   then click **Self-heal** — it re-applies the runbook fix and resolves it.
4. **Self-improving runbooks.** After any resolution, open the service **Runbook** (📕) —
   a new dated *Incident log* entry has been appended automatically.
5. **Dark mode** toggle lives at the bottom of the sidebar.

> The production pipeline (the `incident_analyst` agent + `incident_response` workflow +
> functions) is fully deployed and is what a *real* inbound alert flows through. The
> dashboard's Simulate button models those same decisions on the datastore so a live
> demo never stalls on a serverless cold-start.
