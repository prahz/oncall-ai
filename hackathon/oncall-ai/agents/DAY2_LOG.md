# Day 2 — Agent build + integration test log

Date: 2026-06-27. Pod: `oncall-ai` (cloud). All 4 agents defined as Lemma agents
(JSON bundle, not YAML), POD toolset, name-based grants, structured `output_schema`.

## Model decision (important for Day 3)

The cloud system runtime default model (`minimax-m3`) **could not emit nested tool
arguments** — every `pod_write_record` call came back with empty `data`, so no rows
were written. Fix: pinned all 4 agents to `agent_runtime: { profile_id:
"system:lemma", model_name: "kimi-k2.7-code" }`. With `kimi-k2.7-code` the datastore
writes succeed reliably. Keep this pin (or a comparably capable model) on Day 3
workflow AGENT nodes.

## Agents

| Agent | Reads | Writes | Output |
|---|---|---|---|
| `alert_correlator` | alerts | alerts.correlation_group, alerts.status | grouping summary |
| `root_cause_analyzer` | alerts, runbooks, incidents, on_call_schedule | incidents (create) | incident summary |
| `remediation_suggester` | incidents, runbooks | remediation_actions (create) | actions + decision |
| `post_mortem_writer` | incidents, remediation_actions, alerts | post_mortems (create) | full post-mortem |

Grant note: `root_cause_analyzer` was also granted `on_call_schedule:read` (not in the
original permission list) because its instruction requires looking up the on-call
engineer. Schema additions to `incidents`: `confidence_score` (FLOAT),
`matched_runbook_id` (TEXT), and `correlation_group_id` (TEXT, added for reliable
incident dedup per group).

## Integration test chain (Task 5)

**Step 1 — alert_correlator** (run against 10 `new` alerts)
- Created group `CG-PAY-20260627-001`: 7 alerts (6 payment-service + api-gateway
  cascade) -> status `correlated`.
- Ungrouped 3 (auth-service error_rate, notification-svc queue_depth, infra disk_io)
  -> status `triaged`.

**Step 2 — root_cause_analyzer** (run against `CG-PAY-20260627-001`)
- Created incident `9b62e66a-577e-4b71-929d-20865fb3e0ad`.
- severity `critical`, status `detected`, blast_radius `multi_service`,
  affected_services [payment-service, api-gateway].
- root_cause specific (498/500 pool, 6200->6800ms latency, 34% error rate).
- matched_runbook_id = `af5115ea...` (DB Connection Pool Exhaustion).
- matched_past_incident = `f42c9a44...` (historical DB pool incident, 2026-06-13).
- on_call_engineer = priya@company.com (from on_call_schedule). confidence_score 0.95.
- Idempotency: re-run produced `duplicate_detected: true`, no second incident.

**Step 3 — remediation_suggester** (run against incident `9b62e66a`)
- Created 3 remediation_actions, ALL `auto_approved=false` / `pending_approval`
  (because incident severity is `critical`):
  manual_fix_required (0.95), scale_up (0.90), restart_service (0.82).

**Medium-incident auto-approval test**
- Created test incident `6a27928f...` (severity medium, single_service, matched to
  "High CPU - Scale Up" runbook which is auto_remediation_safe=true, confidence 0.92).
- remediation_suggester produced `scale_up` with `auto_approved=true` / `approved`,
  plus a lower-confidence manual action left `pending_approval`. Auto-approval logic
  verified both directions.

**Step 4 — resolve incident** `9b62e66a` -> status `resolved`, mitigated_at/resolved_at set.

**Step 5 — post_mortem_writer** (run against resolved incident `9b62e66a`)
- Created post_mortems row, status `draft`, 13 timeline events (7 alerts + detection +
  3 actions + mitigated + resolved), all 5 sections populated.
- Idempotency verified separately on historical incident `f42c9a44` (sequential re-run
  did not create a duplicate).

## Known issue observed

A network stream cut ("incomplete chunked read") can leave an agent run executing
server-side after the CLI disconnects. Re-running while the first run is still in
flight caused a brief duplicate post-mortem (two runs raced, neither's dedup check saw
the other). Cleaned up to one row. In Day 3 workflows runs are sequential/orchestrated,
so this race does not apply — but dedup checks remain in each agent as defense.
