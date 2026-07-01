# How to Trigger Fake Alerts for Demos

This guide explains how to simulate incidents to trigger the OnCall-AI workflows. 

## The Setup
The `incident_response` workflow is triggered automatically whenever a new row is inserted into the live `alerts` table in the cloud. To simulate an incident, you simply need to create a mock record in that table using the `lemma` CLI.

We have created two pre-configured scenarios in the `seed/` directory:

### Scenario 1: Human Approval Required (Critical Incident)
This simulates a severe database outage. Because the payload has `"severity": "critical"`, the AI will **never** auto-approve a fix and will escalate it to a human in Slack/Telegram for manual approval.

1. Open your PowerShell terminal.
2. Navigate to the seed directory:
   ```powershell
   cd seed\
   ```
3. Run the trigger script:
   ```powershell
   .\trigger_human.ps1
   ```

### Scenario 2: Automated Fix (Auto-Remediation)
This simulates a medium severity incident for a standard service. Because a runbook exists for this service (`files/runbooks/automated-service.md`) that explicitly says "Auto-remediation safe: yes", the AI can automatically apply the fix without waiting for a human.

1. Open your PowerShell terminal.
2. Navigate to the seed directory:
   ```powershell
   cd seed\
   ```
3. Run the trigger script:
   ```powershell
   .\trigger_automated.ps1
   ```

## Creating Custom Scenarios
If you want to create your own custom alerts for the demo, simply create a new `.json` file with the following structure:

```json
{
  "service": "your-service-name",
  "source": "datadog",
  "severity": "high",
  "message": "Custom error message here."
}
```

Then, you can trigger it directly using the Lemma CLI:
```powershell
lemma record create alerts --file your_custom_file.json
```
