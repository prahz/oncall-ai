# Runbook — payment-service

**Tier:** CRITICAL · money path (card authorization & capture)
**Owner:** payments team · PagerDuty: payments-primary
**Auto-remediation safe: no**

This service moves money. Every remediation risks double-charges, dropped
captures, or reconciliation gaps, so **a human always approves** — the AI
diagnoses and proposes, but never acts alone here.

## Common alerts & what they mean
| Signal | Likely cause |
| --- | --- |
| `error_rate` spike + elevated latency right after a deploy | regression in the new build (bad SDK version, timeout change) |
| declines/timeouts to the card processor | upstream processor incident or a rotated credential |
| latency climbing with steady error rate | DB contention or connection-pool pressure |

## Remediation (in order — all require approval)
1. **Error spike tied to a recent deploy** → propose `rollback_deploy` to the
   last known-good build. Name the suspect deploy. Wait for human approval.
2. **Processor-side declines** → do **not** roll back; page the payments
   on-call and open a vendor ticket. `notify_team`.
3. Never restart mid-transaction without confirming in-flight captures are
   drained.

## Notes for the analyst
- Deploy-linked error spike ⇒ `rollback_deploy`, name `suspect_deploy`,
  confidence can be high **but `runbook_safe = false`** — this is the money path.
- Always route to human approval regardless of confidence.

Auto-remediation safe: no
