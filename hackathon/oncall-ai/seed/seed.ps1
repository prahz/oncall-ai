# ONCALL AI — Day 1 seed script (Windows PowerShell)
#
# Records do NOT travel through `lemma pods import` — this script seeds them via
# `lemma records import` after the tables exist. Timestamps are computed relative
# to "now" at run time so the data stays realistic. Re-running APPENDS rows.
#
# Prereq: tables imported, pod selected (lemma pods select oncall-ai).
# Run from this folder:  powershell -ExecutionPolicy Bypass -File seed.ps1

$ErrorActionPreference = "Stop"
$now = (Get-Date).ToUniversalTime()
function Iso([datetime]$d) { $d.ToString("yyyy-MM-ddTHH:mm:ssZ") }
function Write-Seed($name, $rows) {
  $path = Join-Path $PSScriptRoot "$name.json"
  # @(...) keeps the array wrapper even for single-element collections.
  $json = ConvertTo-Json @($rows) -Depth 10
  # Write UTF-8 WITHOUT a BOM — the lemma records importer rejects a BOM.
  [System.IO.File]::WriteAllText($path, $json, (New-Object System.Text.UTF8Encoding $false))
  return $path
}

# ---------------------------------------------------------------- alerts (10)
$alerts = @(
  [ordered]@{ source="datadog";    service="payment-service";  metric="latency";        severity="critical"; current_value=6200; threshold_breached=2000;  status="new"; timestamp=(Iso $now.AddMinutes(-12)); message="payment-service P99 latency exceeded 6200ms, threshold 2000ms" }
  [ordered]@{ source="datadog";    service="payment-service";  metric="error_rate";     severity="critical"; current_value=0.34; threshold_breached=0.05;  status="new"; timestamp=(Iso $now.AddMinutes(-11)); message="payment-service error rate at 34% (0.34), threshold 5% (0.05)" }
  [ordered]@{ source="cloudwatch"; service="payment-service";  metric="db_connections"; severity="high";     current_value=498;  threshold_breached=450;   status="new"; timestamp=(Iso $now.AddMinutes(-10)); message="DB connection pool at 498/500 - near exhaustion" }
  [ordered]@{ source="grafana";    service="api-gateway";      metric="latency";        severity="high";     current_value=3100; threshold_breached=1000;  status="new"; timestamp=(Iso $now.AddMinutes(-10)); message="api-gateway latency 3100ms exceeded threshold 1000ms" }
  [ordered]@{ source="datadog";    service="payment-service";  metric="cpu";            severity="medium";   current_value=0.91; threshold_breached=0.80;  status="new"; timestamp=(Iso $now.AddMinutes(-9));  message="payment-service CPU at 91% sustained, threshold 80%" }
  [ordered]@{ source="cloudwatch"; service="auth-service";     metric="error_rate";     severity="medium";   current_value=0.12; threshold_breached=0.05;  status="new"; timestamp=(Iso $now.AddMinutes(-8));  message="auth-service error rate at 12% (0.12), threshold 5%" }
  [ordered]@{ source="datadog";    service="payment-service";  metric="latency";        severity="critical"; current_value=6800; threshold_breached=2000;  status="new"; timestamp=(Iso $now.AddMinutes(-7));  message="payment-service P99 latency exceeded 6800ms, threshold 2000ms" }
  [ordered]@{ source="grafana";    service="notification-svc"; metric="queue_depth";    severity="low";      current_value=12000;threshold_breached=5000;  status="new"; timestamp=(Iso $now.AddMinutes(-6));  message="notification-svc queue depth at 12000 messages, threshold 5000" }
  [ordered]@{ source="datadog";    service="payment-service";  metric="memory";         severity="medium";   current_value=0.88; threshold_breached=0.75;  status="new"; timestamp=(Iso $now.AddMinutes(-5));  message="payment-service memory at 88%, threshold 75%" }
  [ordered]@{ source="custom";     service="infra";            metric="disk_io";        severity="low";      current_value=0.95; threshold_breached=0.85;  status="new"; timestamp=(Iso $now.AddMinutes(-3));  message="infra disk I/O utilization at 95%, threshold 85%" }
)

Write-Host "seeding alerts..."
lemma records import alerts (Write-Seed "alerts" $alerts)

# ---------------------------------------------------------------- runbooks (3)
$rb1_symptoms = @"
- DB connection count > 90% of pool size
- Latency spike on payment-service
- Error logs show "connection timeout" or "pool exhausted"
"@
$rb1_steps = @"
1. Check current connection count: ``SELECT count(*) FROM pg_stat_activity``
2. Identify long-running queries: ``SELECT pid, query, now() - pg_stat_activity.query_start AS duration FROM pg_stat_activity WHERE state = 'active' ORDER BY duration DESC``
3. Kill blocking queries if safe: ``SELECT pg_terminate_backend(pid)``
4. Scale up connection pool limit in app config
5. Restart payment-service with ``kubectl rollout restart deployment/payment-service``
6. Verify latency returns to normal within 2 minutes
"@
$rb2_symptoms = @"
- CPU sustained above 85% for 5+ minutes
- Increased response times
- No recent deployment changes
"@
$rb2_steps = @"
1. Confirm CPU spike is sustained, not transient: check last 15 min graph
2. Check for any runaway processes: ``kubectl top pods -n production``
3. Scale up replica count: ``kubectl scale deployment/payment-service --replicas=6``
4. Monitor CPU for next 5 minutes
5. If CPU doesn't drop, escalate to SRE lead
"@
$rb3_symptoms = @"
- Error rate spike immediately following a deployment
- Multiple services showing degraded health
- Blast radius: multi-service or infrastructure
"@
$rb3_steps = @"
1. Identify the most recent deployment: ``kubectl rollout history deployment``
2. Confirm error spike correlates with deploy timestamp
3. Rollback: ``kubectl rollout undo deployment/<service-name>``
4. Verify rollback completes: ``kubectl rollout status deployment/<service-name>``
5. Confirm error rate drops within 3 minutes
6. Notify team in #incidents channel
"@

$runbooks = @(
  [ordered]@{ title="DB Connection Pool Exhaustion"; service="payment-service"; symptoms=$rb1_symptoms; steps=$rb1_steps; success_rate=0.87; auto_remediation_safe=$true }
  [ordered]@{ title="High CPU - Scale Up";           service="payment-service"; symptoms=$rb2_symptoms; steps=$rb2_steps; success_rate=0.79; auto_remediation_safe=$true }
  [ordered]@{ title="Emergency Rollback - Bad Deploy"; service="all-services";  symptoms=$rb3_symptoms; steps=$rb3_steps; success_rate=0.94; auto_remediation_safe=$false }
)
Write-Host "seeding runbooks..."
lemma records import runbooks (Write-Seed "runbooks" $runbooks)

# ---------------------------------------------------------------- incidents (2, both resolved/historical)
$inc1_start = $now.AddDays(-14).Date.AddHours(2).AddMinutes(30)
$inc2_start = $now.AddDays(-30).Date.AddHours(23).AddMinutes(15)
$incidents = @(
  [ordered]@{
    title="DB Connection Pool Exhaustion - payment-service"; severity="high"; status="resolved";
    affected_services=@("payment-service");
    root_cause="Connection pool exhausted due to a slow query introduced in deploy v2.4.1 that caused connections to hold open for 45+ seconds. Pool hit max capacity (500) within 8 minutes of deploy.";
    blast_radius="single_service";
    triggering_alerts=@("datadog:payment-service:latency","cloudwatch:payment-service:db_connections","datadog:payment-service:error_rate");
    on_call_engineer="priya@company.com";
    started_at=(Iso $inc1_start); mitigated_at=(Iso $inc1_start.AddMinutes(21)); resolved_at=(Iso $inc1_start.AddMinutes(40))
  }
  [ordered]@{
    title="API Gateway Latency Spike - cascading from auth-service timeout"; severity="critical"; status="resolved";
    affected_services=@("api-gateway","auth-service","payment-service");
    root_cause="auth-service token validation endpoint introduced a synchronous external call to a third-party KYC provider in deploy v3.1.0. Provider had degraded performance. Every API request blocked waiting for auth. Latency cascaded to api-gateway and payment-service within 4 minutes.";
    blast_radius="multi_service";
    triggering_alerts=@("grafana:api-gateway:latency","cloudwatch:auth-service:error_rate","datadog:payment-service:latency","datadog:api-gateway:error_rate","grafana:auth-service:latency");
    on_call_engineer="james@company.com";
    started_at=(Iso $inc2_start); mitigated_at=(Iso $inc2_start.AddMinutes(29)); resolved_at=(Iso $inc2_start.AddMinutes(47))
  }
)
Write-Host "seeding incidents..."
lemma records import incidents (Write-Seed "incidents" $incidents)

# ---------------------------------------------------------------- on_call_schedule (2, covering next 48h)
$today8 = $now.Date.AddHours(8)
$schedule = @(
  [ordered]@{ engineer="priya@company.com"; start_time=(Iso $today8);            end_time=(Iso $today8.AddDays(1)); timezone="Asia/Kolkata" }
  [ordered]@{ engineer="james@company.com"; start_time=(Iso $today8.AddDays(1)); end_time=(Iso $today8.AddDays(2)); timezone="America/New_York" }
)
Write-Host "seeding on_call_schedule..."
lemma records import on_call_schedule (Write-Seed "on_call_schedule" $schedule)

Write-Host "`nSeed complete."
