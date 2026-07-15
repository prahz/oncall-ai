# Runbook — api-gateway

**Tier:** important · request router (stateless replicas behind a load balancer)
**Owner:** platform team
**Auto-remediation safe: yes**

The gateway proxies traffic to downstream services. Replicas are stateless, so
restarting an unhealthy replica is safe and is the standard fix for the two
failure modes below. A rollback is **not** auto-safe (see bottom).

## Common alerts & what they mean
| Signal | Likely cause |
| --- | --- |
| p95 `latency_ms` over threshold, memory high | **GC thrashing** — heap pressure from a connection/object leak, long GC pauses |
| `latency_ms` spike right after a deploy | bad config or a regression in the new build |
| HTTP 5xx from `/health` | replica crashed or wedged |

## Remediation (in order)
1. **GC thrashing / high latency with no recent deploy** → `restart_service`.
   A restart clears the leaked heap and connection pool. Safe: replicas are
   stateless and drained by the load balancer first.
2. Re-check `/health`: latency back under threshold, memory normal.
3. **Latency spike within ~15 min of a deploy** → `rollback_deploy` to the last
   good build. Rollback touches routing config, so it is **not** auto-safe —
   request human approval.
4. If a restart does not hold after **two** attempts, escalate.

## Notes for the analyst
- GC thrashing / latency with `suspect_deploy = unknown` ⇒ `restart_service`,
  confidence 0.9+.
- Latency clearly tied to a named recent deploy ⇒ `rollback_deploy`,
  `runbook_safe = false` (needs a human).

Auto-remediation safe: yes (restart_service only; rollback_deploy needs human approval)
