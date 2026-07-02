# Automated Service Runbook

This service handles simple, stateless tasks.

## Triage steps
1. Check logs for OOM or panic.
2. Restart the pod if necessary. (Note: Restart tasks must have 0.95+ confidence and 'low' raw_severity)

Auto-remediation safe: yes
