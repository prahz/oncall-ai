# Runbook — database-cluster

**Tier:** CRITICAL · shared stateful infrastructure (primary + replicas)
**Owner:** infra team · PagerDuty: infra-primary
**Auto-remediation safe: no**

The primary datastore for the whole platform. Blast radius is effectively every
service, and the wrong action (failover, restart, cache flush) can cause data
loss or a longer outage. **A human always approves.**

## Common alerts & what they mean
| Signal | Likely cause |
| --- | --- |
| `db.connections.active` at ~100% of pool | **connection-pool exhaustion** — a client leaking connections or a traffic surge |
| replica lag climbing | slow query / long transaction holding locks |
| primary `/health` 5xx | node down — a controlled failover may be required |

## Remediation (in order — all require approval)
1. **Connection-pool exhaustion** → identify the offending client and recycle
   *its* pool (or raise the limit); do **not** blanket-restart the cluster.
   Requires human approval — a restart drops every open transaction.
2. **Primary down** → controlled failover to a healthy replica. Human-driven.
3. Never auto-flush caches or fail over automatically.

## Notes for the analyst
- Connection pool at 100% ⇒ root cause "connection-pool exhaustion", propose the
  targeted fix, `action_type = manual_fix_required` or `notify_team`,
  `runbook_safe = false`.
- Critical + infrastructure blast radius ⇒ always human approval.

Auto-remediation safe: no
