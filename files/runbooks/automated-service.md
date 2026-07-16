# Runbook — automated-service

**Tier:** non-critical · stateless worker
**Owner:** platform team
**Auto-remediation safe: yes**

`automated-service` runs small, stateless, idempotent jobs. It holds no
user-facing state, so a restart is always safe and is the standard first fix.

## Common alerts & what they mean
| Signal | Likely cause |
| --- | --- |
| `/health` or `/ping` unresponsive / HTTP 5xx | process hung or crashed (event-loop block, deadlock) |
| memory_pct climbing over time | slow leak in a worker; cleared by a restart |
| latency_ms spike, CPU normal | GC pause or a stuck downstream call |

## Remediation (in order)
1. **Restart the service** (`restart_service`). It is stateless — a rolling
   restart drops in-flight idempotent jobs safely and clears a hung process.
2. Re-check `/health`: expect `status: healthy`, latency under threshold.
3. If it recovers → done. If it fails **twice**, escalate to a human and check
   logs for a crash loop, OOM kill, or a bad recent deploy.

## Notes for the analyst
- A hung/unresponsive `automated-service` maps cleanly to `restart_service`.
- Clear runbook match + stateless service ⇒ high confidence (0.9+).

Auto-remediation safe: yes
