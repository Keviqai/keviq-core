# Keviq Core Demo Flow

Recommended path for demonstrating Keviq Core capabilities in a browser.

## Prerequisites

- Running Keviq Core stack: `./scripts/bootstrap.sh` (all services healthy)
- Browser at `http://localhost:3000`
- No prior accounts needed (flow starts from registration)

## Demo Steps

### Step 1: Register

Navigate to `/register`. Enter a display name, email, and password (8+ chars).
On success, you are redirected to `/login` with a success banner.

### Step 2: Login

Enter the same credentials. On success, you are redirected to onboarding (first-time user) or the workspace overview.

### Step 3: Create Workspace

On `/onboarding`, enter a workspace name. The slug auto-generates.
Submit to create the workspace and land on the workspace overview.

### Step 4: Launch Demo Task

The workspace overview shows a "Try a demo task" card.
Click **Start demo task** to open the task creation form pre-filled with a demo prompt.
Review, optionally edit, and click **Create Task**.

Alternative: navigate to **Tasks** in the sidebar, click **Create Task**, and write your own prompt.

### Step 5: Watch Task Progress

After creation, you land on the task detail page.
The **Latest Run** card shows the run status (pending → running → completed).
The timeline feed below updates with events in real time.

### Step 6: View Run Details

Click **View Run Details** on the run card.
The run detail page shows execution steps, artifacts produced, and the full timeline.

### Step 7: Inspect Artifact

In the **Artifacts** section of the run detail, click any artifact name.
The artifact detail page shows:
- Inline preview (markdown renders formatted, JSON pretty-printed, text as-is)
- Download button (for ready artifacts)
- Provenance chain (model, temperature, tool used)
- Lineage graph (parent artifacts, if any)

### Step 8: Browse All Artifacts

Navigate to **Artifacts** in the sidebar to see all workspace artifacts.

### Optional: Terminal

From the run detail page, if a sandbox exists, click the **Terminal** button (top right).
Type commands in the terminal to inspect the sandbox environment.

## Expected Outputs

- A task in `completed` status with one run
- At least one artifact (e.g., a markdown report) in `ready` status
- The artifact preview renders inline on the detail page
- Timeline shows task.submitted → run.queued → run.started → run.completed events

## Fallback Guidance

| Symptom | Check |
|---------|-------|
| No run appears after task creation | Verify orchestrator is running: `curl localhost:8001/healthz/live` |
| Run stays in `queued` | Verify agent-runtime is running: `curl localhost:8002/healthz/live` |
| Run fails immediately | Check orchestrator logs for agent configuration or model endpoint issues |
| No artifacts appear | Verify artifact-service is healthy: `curl localhost:8003/healthz/live` |
| Preview says "unsupported" | Only text, JSON, and markdown artifacts render inline; download instead |

## Deployment Profile

Use the `local` profile (default) for demo. This runs all services on a single Docker Compose stack.
The `hardened` profile adds TLS and stricter auth but requires certificate setup.

## Smoke Verification

Run `./scripts/smoke-test.sh` to verify all services are healthy before the demo.
