# OnCall AI — Complete Guide

This document explains the **entire** OnCall AI app end-to-end: what it is, how it's
built on the Lemma platform, every table/function/agent/workflow/schedule, how the
multi-tab dashboard works, the incident lifecycle, theming, Slack/Telegram wiring, how
to deploy, and the important platform constraints that shaped the architecture. Read it
top to bottom and you'll understand the whole system.

---

## 1. What it is

**OnCall AI** is "the AI on-call engineer for teams without an SRE." It watches a
project's CI/CD and services, and when something breaks it:

1. **Triages** the failure (root cause, severity, a transparent triage score),
2. **Decides** autonomously whether it can fix it or needs a human (runbook-gated),
3. **Delegates** the fix to an **AI solver agent** (which writes a code patch, runs
   tests, opens a PR) or to a **human**,
4. **Pushes** the fix, resolves the incident, writes a **blameless post-mortem**, and
5. **Notifies** the team on **Slack / Telegram** at every step.

It is a **Lemma Pod** — built from Lemma primitives (tables, functions, agents,
workflows, schedules, connectors, surfaces) plus a custom web **app** (the dashboard).

### The demo product story
The dashboard is a "mission control" for a mock software org with demo projects
(`shopfront-web`, `payments-api`). You **simulate a CI/CD failure**, watch OnCall AI
pull it in, triage it, auto-fix or ask for approval, hand it to the solver agent which
shows a **live coding console + real diff + PR**, push it, and see the project go green
again — with Slack pings throughout.

---

## 2. Cloud target (READ THIS BEFORE DEPLOYING)

There are several look-alike pods on this account. The **one true pod** is:

| Field | Value |
| --- | --- |
| Org | `harshdumpss-s-space` = `019eff2e-a06b-7647-b98a-605385ee80aa` |
| Pod | **`Oncall-AI`** = `019f1e93-f5f6-766f-b9c0-1606bc2809be` |
| Dashboard URL | https://oncall-dashboard-harsh-dev.apps.lemma.work |
| App public_slug | `oncall-dashboard-harsh-dev` |

`deploy.ps1` pins `--org` and `--pod` to these so a deploy can never hit the wrong pod.
Always deploy through it. `pod.json`'s `name` is `oncall-ai` but the live pod is the
capitalized `Oncall-AI` — do not get confused; the ID is what matters.

---

## 3. Two runtime realities (the single most important thing to understand)

There are **two** ways incidents can be driven, and it matters:

### (a) The production pipeline — agents + functions + workflows
The "real" Lemma pipeline: a row inserted into the `alerts` table triggers the
`incident_response` workflow (via the `alert_trigger` datastore schedule), which runs the
`incident_analyst` agent, the safety-gate functions, approval, remediation, and the
`postmortem_writer` agent. Fully deployed; this is what a genuine external alert flows
through.

### (b) The dashboard — datastore-driven (what the demo actually uses)
**This pod's serverless FUNCTION tier is badly degraded — every function cold-starts for
~90 seconds and often fails with "sandbox temporarily unavailable."** That makes the
multi-step workflow unusable for a live demo (it fails on step 1). So the **dashboard
drives the entire incident lifecycle directly on the datastore** from the browser
(`client.records.create/update`), reading the real `runbooks` table and computing the
real triage formula in JS. It does **not** insert `alerts` rows, so it deliberately does
**not** trigger `incident_response` — that's why that workflow shows no recent runs, and
it's expected, not broken.

Consequences:
- Simulations are **instant and reliable**; nothing waits on cold functions.
- Slack/Telegram are sent **directly from the browser** via the connector
  (`client.connectors.operations.execute`), not via the (slow) `notify` function.
- The agents/functions/workflows remain deployed as the authentic production path and
  for code review; the demo just doesn't depend on them.

**Corollary:** file writes via the local CLI are broken by version skew
(`INVALID_MULTIPART_FIELD 'path'`), but the browser JS SDK and the pod runtime CAN write
files. Post-mortems are written to `/postmortems/INC-<n>.md` from the browser
(`client.files.upload`). Also: Git Bash mangles `/postmortems`-style paths into
`/C:/Program Files/Git/...` — use the PowerShell tool or `MSYS_NO_PATHCONV=1` for
`lemma file` commands.

---

## 4. Directory structure

```
pod.json                     Pod identity + connector account variables (slack_account, telegram_account)
deploy.ps1                   Pinned deploy script (org+pod), runs _bootstrap, deploys the app
scripts/build_bootstrap.py   Re-embeds files/runbooks/*.md into the _bootstrap function
agents/                      incident_analyst, oncall_responder, postmortem_writer
functions/                   all Python functions (see §6)
workflows/                   incident_response, health_check, heal, daily_stats_wf
schedules/                   alert_trigger, health_poll, heal, daily_stats
surfaces/                    slack, telegram (chat surfaces backed by oncall_responder)
tables/                      the data model (see §5)
files/runbooks/*.md          human-readable runbook source (loaded into the runbooks TABLE)
files/postmortems/           folder for generated post-mortems (written at runtime)
apps/oncall-dashboard/       the dashboard app (source/index.html is the whole SPA)
seed/                        legacy CLI trigger scripts (superseded by the dashboard)
```

Note: `functions/_bootstrap` is the one-shot seed function (keep it). `functions/_filetest`
and `functions/inspect` are throwaway probes — safe to delete.

---

## 5. Data model (tables)

Every table is `visibility: POD`, RLS off.

### `projects` — the mock sandbox projects
`id, name, slug, provider(demo|github|gitlab|custom), repo_url, default_branch,
description, emoji, connected(bool)`. Seeded with `shopfront-web` (github) and
`payments-api` (gitlab). "Connect a repo" in the Sandbox creates more.

### `ci_runs` — CI/CD pipeline runs (the sandbox log feed)
`id, project_id→projects, pipeline, run_number, ref, commit_sha, commit_msg,
status(passing|running|failing|fixed), stage, service, error_signature, logs(text),
incident_id→incidents`. A "Simulate failure" creates a `failing` run; when the fix is
pushed the run flips to `fixed` and a new green `🤖 fix: …` run is appended.

### `incidents` — the core incident record
`id, number(SERIAL, "INC-<n>"), title, service, severity(critical|high|medium|low),
status(detected|triaging|mitigating|resolved|post_mortem_pending), blast_radius
(single_service|multi_service|infrastructure), root_cause, confidence(0–1),
suggested_fix, suspect_deploy, affected_services(json), triggering_alerts(json — the
dashboard stores the alert as an OBJECT here, not just ids), project_id, ci_run_id,
triage_score(int), triage_reason(text — the score breakdown), heal_attempts(int),
postmortem_md(text — rendered in the dashboard), postmortem_path(file path),
mitigated_at, resolved_at`.

### `remediation_actions` — the proposed/executed fix + approval gate
`id, incident_id, action_type(restart_service|scale_up|rollback_deploy|clear_cache|
notify_team|manual_fix_required), description, confidence, auto_approved(bool),
status(pending_approval|approved|executed|failed|rejected), executed_by(agent|email),
result`.

### `delegations` — who does the fix (kanban board)
`id, incident_id, project_id, ci_run_id, title, assignee_type(agent|human), assignee,
status(queued|working|solved|pushed|rejected|failed), summary, pr_url, notes`.

### `runbooks` — the AI's knowledge base (NOT files)
`id, service(unique), title, tier, auto_safe(bool — the deterministic
"may the AI auto-remediate?" verdict), content(markdown)`. Read by the analyst /
triage gate / heal. Editable in the Runbooks tab. Source markdown lives in
`files/runbooks/*.md` and is embedded into `_bootstrap`.

### `alert_rules` — per-project/per-event Slack/Telegram control
`id, project_id(null = all projects), channel(slack|telegram), event(manual_approval|
escalation|delegation_agent|delegation_human|incident_resolved|daily_stats),
enabled(bool), target(optional channel-id override), label`.

### `notification_settings` — connector wiring per channel
`id, channel, label, enabled, auth_config, send_operation, target_field, account_id,
incidents_target, escalations_target`. Holds the connector operation + default channel/chat ids.

### `monitored_services` — services the production health poll watches
`service, enabled, base_url, health_path, remediate_path, latency/memory thresholds,
control_token, last_status, last_checked_at, last_detail`. Seeded disabled (demo).

### `alerts` — raw inbound monitoring events (production path only)
`service, source, severity, metric, current_value, threshold, message, status,
correlation_group, incident_id`. The dashboard does **not** write here.

---

## 6. Functions (Python, Lemma)

- **`dedupe_and_correlate`** — first workflow step: attach a new alert to an open
  incident / mark duplicate, or decide `new_incident`.
- **`open_incident`** — the **safety-critical, deterministic** step. Reads the alert's
  real severity, checks `runbooks.auto_safe`, computes the **transparent triage score**
  (severity + blast radius + off-hours + low-confidence risk, 0–100, with a per-factor
  `triage_reason`), decides `auto_approve_eligible`, and creates the incident +
  remediation_action. The LLM proposes; this function decides what's safe.
- **`triage_score`** — standalone, explainable version of the same scoring formula.
- **`execute_remediation`** — applies the fix; does a REAL http re-check only for an
  `enabled` monitored service, otherwise simulates healthy; resolves or escalates.
- **`heal`** — scheduled self-healing: finds incidents stuck in `mitigating`, re-reads
  the runbook, retries the fix up to 3× (or escalates if the runbook isn't auto-safe).
- **`notify`** — multi-channel notifier (reads notification_settings, posts to
  slack/telegram). Used by the production path; the dashboard sends directly instead.
- **`resolve_approval`** — lets a human approve/reject from Slack/Telegram chat by
  resolving the matching WAITING workflow run's form.
- **`publish_postmortem`** — writes `incidents.postmortem_md` out to a real
  `/postmortems/INC-<n>.md` file and sets `postmortem_path`.
- **`daily_stats`** — computes an ops digest and posts it to enabled channels (driven by
  the `daily_stats` cron).
- **`probe_service`** — production health poll: HTTP-checks enabled monitored_services
  and opens alerts on breach.
- **`_bootstrap`** — one-shot seed: loads `files/runbooks/*.md` (base64-embedded) into
  the `runbooks` table and seeds `monitored_services`. Idempotent. Run by `deploy.ps1`.

---

## 7. Agents

- **`incident_analyst`** (`deepseek-v4-pro`) — reads the triggering alert, looks up the
  service's `runbooks` row, returns a structured diagnosis (title, root_cause,
  blast_radius, confidence, suggested_fix, action_type, runbook_safe, suspect_deploy).
  Analysis only; never writes tables.
- **`oncall_responder`** — the agent behind the Slack & Telegram surfaces. Reads intent
  ("approve INC-42") and calls `resolve_approval`; answers status questions.
- **`postmortem_writer`** — after resolution, composes a blameless post-mortem, writes it
  to `incidents.postmortem_md`, and **appends a dated "lesson" entry to the service's
  `runbooks.content`** (self-improving runbooks). A downstream function publishes the file.

---

## 8. Workflows & schedules

Workflows:
- **`incident_response`** (DATASTORE_EVENT on `alerts` INSERT) — dedupe → is_new →
  analyze (agent) → open_incident (safety gates) → auto_route → execute **or**
  notify+approval(FORM)+approved_route → notify_resolved → resolved_route → postmortem
  (agent) → publish_postmortem → done.
- **`health_check`** (cron) — wraps `probe_service`.
- **`heal`** (cron) — wraps the `heal` function.
- **`daily_stats_wf`** (cron) — wraps `daily_stats`.

Schedules:
- **`alert_trigger`** — DATASTORE trigger firing `incident_response` on `alerts` INSERT.
- **`health_poll`** — every minute → `health_check`.
- **`heal`** — every 2 minutes → `heal`.
- **`daily_stats`** — cron `0 9 * * *` (09:00 UTC) → `daily_stats_wf`. **Editable from the
  dashboard** (Alerts tab writes its `config.cron` via `client.schedules.update`).

---

## 9. Surfaces & notifications (Slack / Telegram)

- `surfaces/slack` and `surfaces/telegram` back the `oncall_responder` agent (chat).
- Sending is done from the **browser** via
  `client.connectors.operations.execute({organizationId, authConfigName}, operation,
  {body:{channel|chat_id, text}}, account_id)`.
- **Routing** = `notifyChannels(event, incident, projectId)`: for each enabled
  `notification_settings` row it checks `alert_rules` (is this event enabled for this
  channel/project?) and resolves the target (an `alert_rules.target` override, else the
  channel's escalations/incidents target).
- **Dedicated delegation channels** (already wired):
  - `delegation_agent` → Slack channel **`C0BHQ0RS69Y`** (agent-delegation)
  - `delegation_human` → Slack channel **`C0BHTMR74S0`** (human-delegation)
  - Default incidents/escalations channel is `C0BDU08MWFN`.
  - The Slack bot must be a member of any channel it posts to.

Events: `manual_approval`, `escalation`, `delegation_agent`, `delegation_human`,
`incident_resolved`, `rejected`, `daily_stats`.

---

## 10. The dashboard app (`apps/oncall-dashboard/source/index.html`)

A **single self-contained SPA** (one HTML file: CSS + vanilla JS + the Lemma browser SDK
loaded from `/public/sdk/lemma-client.js`). It authenticates as the viewer, seeds the two
demo projects on first load (`ensureSeed`), loads all tables (`loadAll`), watches
`incidents/ci_runs/delegations` for live updates, and polls every 6s. Six tabs:

### Overview
KPI row (Active incidents, Avg time-to-resolve/MTTR, Auto-resolved %, Resolved), a 14-day
**incident-volume area chart**, a **resolution-outcomes** segmented bar
(agent/human/escalated), an **incidents-by-severity** bar list, and a **Recent activity**
audit feed. Topbar: **Play full demo** (auto-runs a full incident) and **Reset** (wipes
incidents/delegations + simulated CI runs to a clean board).

### Sandbox (mission control)
Project rail (health badges) + per-project: a **Live preview** (mock browser frame — a
running site when healthy, a red "502 · Application error" when failing), **Service
metrics** (Grafana-style request-rate / error-rate / p95-latency / memory area charts
that spike red when unhealthy), **CI/CD pipeline runs** (with a log viewer), and a **Live
logs** tail. Topbar **Simulate failure** injects one of 5 CI-failure scenarios.

### Incidents
KPIs + a filterable incident list + a detail pane: severity/status, project/service,
root cause, suggested fix, **triage-score gauge with the full breakdown**, a **timeline**
(alert → actions → delegation → resolved), and links (📄 post-mortem, 📕 runbook, 📜 CI
logs, 🤖 agent fix & diff). Pending incidents show an inline **Approve & delegate /
Reject**.

### Delegations
An **Autonomy & routing settings** panel (see below) + a **skeuomorphic kanban** (Queued
/ In progress / Pushed) of raised, tactile cards (blue rail = agent, gray = human). This
is where the **solver agent** runs: `agentSolve` opens a live **console modal** that
clones the repo, shows the **actual code diff**, runs tests, commits and opens a PR, then
`pushFix` marks the ci_run fixed, resolves the incident, writes the post-mortem, and
appends the runbook lesson. Human delegations get **Solve & push** / **Let agent handle
it**. "View agent work" replays the diff+PR.

### Runbooks
Full **CRUD** with a split-pane **markdown editor** (live preview + formatting toolbar),
metadata fields (service/title/tier + **auto-remediation-safe** toggle), **file upload**
(.md/.txt read in-browser), a template with Signals/Cause/Fix/**Rules** sections, and
delete. Saves to the real `runbooks` table the AI reads.

### Alerts & schedules
- **Channels**: Slack/Telegram cards — connected status, enable toggle, editable
  incidents/escalations channel ids, **Send test** per channel.
- **Scheduled digest**: frequency (Daily/Weekdays/Weekly/Hourly) + time picker → rewrites
  the `daily_stats` cron via `client.schedules.update`.
- **Notification rules**: event × Slack/Telegram matrix, scoped per project, with
  per-event channel routing (the delegation channel ids live here).
- Topbar: **Send daily digest** and **Send test approval**.

### Key JS concepts
- `SETTINGS` (localStorage `oncall-settings`) = `{autoMode, threshold, maxSev, noInfra}`
  — the **autonomy dial** (lives on the Delegations tab). Drives `routeType()` (agent vs
  human by severity) and the auto-approve gate in `simulateFailure`. **These only tighten
  the runbook's auto_safe verdict, never loosen it.**
- `SCEN` = the 5 CI-failure scenarios; `FIXES` = the per-service code diff/commit/test the
  solver agent "writes".
- `triage()` = the deterministic score formula (mirrors `open_incident`).
- The whole lifecycle is datastore ops; there is no dependency on the slow functions.

### Theming
Six themes via a sidebar **Theme** selector (persisted in localStorage `oncall-theme`),
each a full set of CSS variables:
- **Resend** (default — pure black, hairline borders, blue accent, glass, sentence case),
  **Linear** (graphite+indigo), **Grafana** (dark+orange, flat panels), **Harness**
  (navy+cyan), **CodeRabbit** (warm dark+orange), **Light**.
All components (and SVG charts, via `style="…var(--x)…"`) recolor live. Dark-specific
CSS uses `:root:not([data-theme="light"])` so every dark theme gets it.

---

## 11. Incident lifecycle (dashboard path, end-to-end)

1. **Sandbox → Simulate failure** creates a `failing` `ci_run` + an `incident` (triaged
   with the real score) + a `remediation_action`.
2. **Triage** decides auto vs approval: `auto_ok = SETTINGS.autoMode && runbook.auto_safe
   && confidence ≥ threshold && severity ≤ maxSev && !(noInfra && infrastructure)`.
3. **Auto path**: incident → `mitigating` → an **agent delegation** is created → the
   **solver console** streams (diff, tests, PR) → push. **Approval path**: a Slack
   `manual_approval` is sent; you **Approve** in the Incidents detail → a delegation is
   created and **auto-routed by severity** (critical → human, else agent).
4. **Delegation** (agent auto-progresses, or human hits Solve & push): on push the
   `ci_run` → `fixed`, a green `🤖 fix` run is appended, the incident → `resolved`, the
   **post-mortem** is written (table + `/postmortems` file) and a **runbook lesson**
   appended, and `incident_resolved` is posted to Slack.
5. **Sandbox** reflects it: preview goes green, metrics recover.
6. **Self-heal**: any incident left `mitigating` is recovered by the heal logic.

---

## 12. Deploying & running

**Deploy everything** (from repo root, on Windows PowerShell):
```powershell
.\deploy.ps1
```
It imports `tables, functions, agents, workflows, schedules, surfaces` (pinned to the
canonical pod), runs `_bootstrap` (seeds runbooks + monitored_services), and deploys the
app (renaming `package.json` to dodge the Windows `npm ci` WinError 2).

**After editing a runbook** (`files/runbooks/*.md`): `python scripts/build_bootstrap.py`
then `.\deploy.ps1` (re-embeds + re-seeds). Or just edit it in the Runbooks tab.

**App-only redeploy**: `lemma --org <ORG> --pod <POD> apps deploy oncall-dashboard
apps/oncall-dashboard/source -y` (rename `package.json` aside first).

**Run/demo**: open the dashboard, **Overview → Play full demo**, then **Sandbox →
Simulate failure**, walk through Incidents → Delegations (watch the solver console) →
Sandbox goes green → Alerts → Send test. Pick a Theme to taste.

---

## 13. Constraints & decisions (why things are the way they are)

- **Serverless functions cold-start ~90s / flake on this pod** → the dashboard is
  datastore-driven; the demo never waits on functions. The production workflow is still
  deployed for authenticity/real alerts.
- **Local CLI is version-skewed** (SDK 3.1.0 vs server 4.0.1): `workflow runs list/get`
  crash (`KeyError flow_id`) and `file upload/write` fail (`INVALID_MULTIPART_FIELD`).
  The **cloud runtime and browser SDK are fine.**
- **Git Bash mangles `/…` paths** for `lemma file` — use PowerShell or `MSYS_NO_PATHCONV=1`.
- **Runbooks & post-mortems live in tables** (`runbooks.content`, `incidents.postmortem_md`)
  for reliability; post-mortems are additionally published to `/postmortems` files from
  the browser SDK.
- **Guardrails (trust):** the runbook's `auto_safe` is the ceiling on autonomy; the
  autonomy dial can only tighten it; critical/infrastructure/money-path always route to a
  human; every fix is a reviewable PR.

---

## 14. Quick reference

- Live dashboard: https://oncall-dashboard-harsh-dev.apps.lemma.work
- Org / Pod: `019eff2e-a06b-7647-b98a-605385ee80aa` / `019f1e93-f5f6-766f-b9c0-1606bc2809be`
- Slack channels: incidents/escalations `C0BDU08MWFN`, agent-delegation `C0BHQ0RS69Y`,
  human-delegation `C0BHTMR74S0`
- Whole UI lives in one file: `apps/oncall-dashboard/source/index.html`
- Deploy: `.\deploy.ps1`
