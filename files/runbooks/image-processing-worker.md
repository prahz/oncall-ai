# Runbook — image-processing-worker

**Tier:** important · async worker (pulls jobs from a queue)
**Owner:** media team
**Auto-remediation safe: yes**

Decodes and resizes images off a job queue. Jobs are re-queued on worker exit,
so a restart never loses work. Known to leak native memory from the image
decoder under sustained load, which ends in an OOM kill.

## Common alerts & what they mean
| Signal | Likely cause |
| --- | --- |
| `memory_pct` climbing toward 100%, then OOM | **native memory leak** in the decode path (the classic failure) |
| worker `/health` 5xx after OOM | kernel OOM-killed the process; it needs a clean restart |
| queue depth rising, throughput dropping | worker wedged on a poison-pill image |

## Remediation (in order)
1. **Memory leak / OOM kill** → `restart_service`. The queue redelivers
   in-flight jobs, so this is safe and clears the leaked native heap.
2. Re-check `/health`: `memory_pct` back to baseline, worker consuming the queue.
3. If OOM recurs within one poll cycle after a restart, escalate — likely a
   poison-pill job or a regression; a human should drain the queue / patch the
   decoder.

## Notes for the analyst
- Rising memory ending in OOM ⇒ `restart_service`, confidence 0.9+.
- This is a recurring, well-understood leak, so auto-remediation is safe for a
  first restart.

Auto-remediation safe: yes
