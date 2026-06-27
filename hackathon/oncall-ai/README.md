# ONCALL AI

Autonomous incident response platform for SRE/DevOps teams. Ingests alerts from
monitoring tools, correlates them into incidents, suggests/auto-executes
remediation, and writes post-mortems.

**Status:** Day 1 — schema + seed data only. No agents/workflows/functions yet.

## Pod structure

```
oncall-ai/
  pod.json
  tables/            6 tables (alerts, incidents, runbooks,
                     remediation_actions, post_mortems, on_call_schedule)
  agents/            (empty — Day 2+)
  workflows/         (empty — Day 2+)
  functions/         (empty — Day 4+)
  surfaces/          (empty — Day 2+)
  apps/dashboard/    (empty — Day 5)
  seed/              seed.ps1 + generated *.json (NOT imported by pod import)
```

> Note on conventions: Lemma bundles are **JSON, not YAML**, one folder per table
> (`tables/<name>/<name>.json`). `id`, `created_at`, `updated_at` are
> system-managed (never declared). Foreign keys use type `UUID` referencing
> `incidents.id`. There is no top-level `permissions/` directory — permissions are
> `permissions.grants` embedded in each agent/function JSON (added Day 2+).
> All tables are shared team data (`enable_rls: false`).

## Setup

```powershell
# 1. Create + select the pod (once)
lemma pods create oncall-ai --description "ONCALL AI - autonomous incident response platform"
lemma pods select oncall-ai --save-default

# 2. Import the schema (tables only — records do not travel in the bundle)
lemma pods import ./oncall-ai --dry-run
lemma pods import ./oncall-ai

# 3. Seed records (timestamps are computed relative to now at run time)
cd oncall-ai/seed
powershell -ExecutionPolicy Bypass -File seed.ps1
```

## Seed contents

- **alerts** — 10 rows, a realistic burst (T-12min … T-3min). Mixed severities
  (3 critical / 2 high / 3 medium / 2 low) and sources. `correlation_group` is
  left **null** on every row (the `alert_correlator` agent fills it on Day 2).
  Alert 7 (payment-service latency 6800ms) is a near-duplicate of Alert 1
  (6200ms) — kept for the `deduplicate_alerts` function on Day 4.
- **runbooks** — 3 rows. Two `auto_remediation_safe: true` (DB Connection Pool
  Exhaustion 0.87, High CPU 0.79), one `false` (Emergency Rollback 0.94).
- **incidents** — 2 historical resolved incidents (14 and 30 days ago) with full
  `root_cause` text, for the `root_cause_analyzer` to pattern-match against.
- **on_call_schedule** — 2 shifts covering the next 48h (priya@ Asia/Kolkata,
  then james@ America/New_York).

## Verify

```powershell
lemma query run "select severity, count(*) n from alerts group by severity"
lemma query run "select count(*) from alerts where correlation_group is null"   # expect 10
lemma query run "select title, auto_remediation_safe, success_rate from runbooks"
lemma query run "select title, status from incidents"                            # both resolved
lemma query run "select engineer, timezone from on_call_schedule order by start_time"
```

---

## Day 2 — Agents (the brain)

Four Lemma agents (`agents/<name>/<name>.json` + `instruction.md`), each with the
`POD` toolset and explicit name-based grants. See `agents/DAY2_LOG.md` for the full
build + integration-test log.

```
alerts (new) -> [alert_correlator] -> [root_cause_analyzer] -> incidents
                                                  |
                                                  v
                          [remediation_suggester] -> remediation_actions
                                                  |
                          (incident resolved) -> [post_mortem_writer] -> post_mortems
```

| Agent | Reads | Writes |
|---|---|---|
| `alert_correlator` | alerts | alerts (correlation_group, status) |
| `root_cause_analyzer` | alerts, runbooks, incidents, on_call_schedule | incidents |
| `remediation_suggester` | incidents, runbooks | remediation_actions |
| `post_mortem_writer` | incidents, remediation_actions, alerts | post_mortems |

**Model pin (required):** all agents set `agent_runtime.model_name = "kimi-k2.7-code"`.
The default `minimax-m3` failed to emit nested tool-call arguments, so datastore
writes silently no-op'd. Keep a capable model pinned on Day 3 workflow AGENT nodes.

**Schema additions on `incidents` (Day 2):** `confidence_score` (FLOAT),
`matched_runbook_id` (TEXT), `correlation_group_id` (TEXT — enables incident dedup).

### Run the chain

```powershell
lemma agents run alert_correlator "Process all alerts in status 'new'..."
lemma agents run root_cause_analyzer "Analyze correlation group CG-PAY-YYYYMMDD-001..."
lemma agents run remediation_suggester "Propose remediation for incident <id>..."
# mark incident resolved, then:
lemma agents run post_mortem_writer "Write a post-mortem for resolved incident <id>..."
```
