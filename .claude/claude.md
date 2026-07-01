# OnCall AI - AI Coding Agent Guidelines

This document provides essential context and instructions for AI coding agents working on the OnCall AI repository. The sections are ordered to progressively build context, starting from high-level project goals down to specific execution commands.

## 1. What the project is
**OnCall AI** is an automated system described as "The AI on-call engineer for teams without an SRE." It is designed to assist with incident response, monitor system reliability, and automate typical on-call engineering tasks. The project is built as a **Lemma Pod**, utilizing various AI agents, workflows, and integrations (like Slack).

## 2. Where things live
Understanding the directory structure is critical. The repository follows a standard Lemma pod architecture:

- **`pod.json`**: The root configuration file defining the pod's identity, version, and environment variables (e.g., Slack connector accounts).
- **`agents/`**: Definitions and prompts for the AI agents that handle on-call reasoning and interactions.
- **`apps/`**: Custom user-facing applications.
  - **`apps/oncall-dashboard/source/`**: The frontend web dashboard for viewing and managing on-call data.
- **`workflows/`**: Automated step-by-step processes for handling incidents or alerts.
- **`functions/`**: Custom executable code or tools that agents and workflows can invoke.
- **`schedules/`**: Cron jobs and scheduled tasks for recurring checks.
- **`surfaces/`**: Chat interfaces and integrations (e.g., Slack bots).
- **`tables/`**: Database schemas and data storage definitions.
- **`files/`**: Static assets and auxiliary files.

## 3. How work gets done
Development in this repository is split between Lemma platform primitives and custom web applications:
- **Lemma Components:** Work involves creating or modifying configuration files (JSON/YAML) and scripts within `agents/`, `workflows/`, `functions/`, and `surfaces/`. These define the AI's behavior and integrations.
- **Dashboard Development:** The UI is located in `apps/oncall-dashboard/source/`. Changes to the UI involve modifying HTML/CSS/JS or Node.js code within this specific directory.
- **Environment & Variables:** When adding new integrations, always check or update `pod.json` to ensure the required variables (like API keys or connector accounts) are declared.

## 4. How to build
- **Lemma Pod:** Lemma primitives (agents, workflows, tables) are declarative and do not require a traditional compilation step. They are synced/deployed directly to the Lemma platform.
- **Dashboard App:** Currently, the dashboard app in `apps/oncall-dashboard/source/` is a lightweight web application without a complex build pipeline (no Vite/Webpack configured). It runs directly from the source.

## 5. How to run tests
- **Dashboard Verification:** To run and manually test the dashboard locally:
  1. Navigate to `apps/oncall-dashboard/source/`
  2. Run `npm start` (which executes `npx serve .`) to serve the files locally.
- **Automated Tests:** There are currently no automated unit or integration test scripts defined in the repository (e.g., no `npm test` script in `package.json`). 
- **End-to-End Testing:** Testing the core AI logic requires deploying the pod to a Lemma environment and triggering the relevant workflows or interacting with the configured Slack surface.

## 6. How to deploy / sync to cloud
When pushing the latest local version to the cloud using `lemma pod import .` on Windows, you may encounter a known error:
```
app building oncall-dashboard: npm ci
[WinError 2] The system cannot find the file specified
```
This happens because the Python subprocess driving the CLI fails to execute the Windows `npm.cmd` script without a shell.

**Workaround:** Instead of importing the entire directory at once, use a PowerShell loop to individually push all backend resources, completely bypassing the app compilation step:

```powershell
$dirs = @("agents", "functions", "schedules", "surfaces", "tables", "workflows")
foreach ($dir in $dirs) {
    if (Test-Path $dir) {
        Write-Host "Importing $dir..."
        lemma pod import $dir
    }
}
```

If you add new static files (like runbooks), you can sync them explicitly:
`lemma file upload ./files/runbooks/your-file.md /runbooks/your-file.md`
