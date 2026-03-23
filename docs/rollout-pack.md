# Keviq Core — Broader Usage Rollout Pack

> Prepared: 2026-03-23
> Status: READY FOR BROADER USAGE
> Smoke: 21/21 PASS
> UAT: 28 cases (22 PASS, 4 CONDITIONAL PASS, 0 FAIL)

---

## 1. Rollout Readiness Summary

### What is ready

- **21/21 user journeys verified** — all core flows functional end-to-end
- **Task lifecycle**: create → edit brief → review → launch → result with formatted output
- **Artifact pipeline**: register → finalize → inline preview with rendered markdown + GFM tables
- **Collaboration**: comments on tasks, activity feed with comment events, Needs Review queue
- **Observability**: task/run timeline, provenance tracking, /health dashboard
- **Model integration**: Claude Bridge path produces real AI-generated outputs
- **UTF-8 correctness**: em-dashes, smart quotes, Unicode punctuation render correctly
- **Session management**: login, workspace selector, session-expiry notification
- **Smoke test**: 21/21 checks pass consistently

### Caveats

- Claude Bridge must be manually started for model-backed tasks
- Activity feed shows Task submitted/started events (meaningful but verbose)
- /health page is operator-facing — stale scrape timestamps, no sidebar
- Artifact type shows "model_output" instead of friendlier label
- Run detail shows "Attempt #" without the actual number
- No token auto-refresh — session expires after token TTL (with banner warning)

---

## 2. Tester Quickstart

### Getting started

1. Open **http://localhost:3000** in your browser
2. Log in with your test credentials
3. You'll land on the **Workspace Home** — this is your dashboard

### What to try first

1. Click **"+ New Task"** (top right, blue button)
2. Enter a title and fill in the Goal, Context, Constraints, and Desired Output fields
3. Pick an agent (Research Analyst is a good default)
4. Click **Save Draft**, then **Review & Launch**
5. On the review page, click **Launch Task**
6. Wait 15–30 seconds for the agent to complete
7. On the task detail page, look for the green **"Task completed"** banner
8. Click **"View Output →"** to see the formatted result

### Where to find things

| What | Where |
|------|-------|
| Tasks | Sidebar → Tasks |
| Results | Task detail → green banner → "View Output →" |
| Activity | Sidebar → Activity |
| Review queue | Sidebar → Needs Review |
| System status | Sidebar → System Health |

---

## 3. Controlled Usage Checklist

```
MONAOS BROADER USAGE CHECKLIST
Date: ___________
Tester: ___________

[ ] 1. LOGIN
    - Open http://localhost:3000
    - Log in with test credentials
    - Confirm: user name visible in top-right? workspace name visible?

[ ] 2. WORKSPACE HOME
    - Stat cards visible (Drafts / Active / Pending Approvals)?
    - Recent Tasks section shows previous tasks?
    - "+ New Task" button visible?

[ ] 3. CREATE A TASK
    - Click "+ New Task"
    - Enter a real title and brief (Goal, Context, Constraints, Desired Output)
    - Select an agent
    - Click "Save Draft"
    - Confirm: "Draft saved successfully" message appears?

[ ] 4. REVIEW AND LAUNCH
    - Click "Review & Launch →"
    - Review page shows brief summary + agent info + risk level?
    - Click "Launch Task"
    - Confirm: redirected to task detail without error?

[ ] 5. VIEW RESULT
    - Wait for task to complete (15-30 seconds)
    - Green "Task completed" banner visible?
    - Output name and snippet shown?
    - Click "View Output →"
    - Confirm: artifact detail page loads with preview?

[ ] 6. ARTIFACT PREVIEW
    - Rendered/Raw toggle visible?
    - Headings, bold, lists render correctly?
    - If output has a table, does it render as a formatted grid?
    - Provenance line shows model/provider info?
    - Download / Copy link / Export buttons work?

[ ] 7. ADD COMMENTS
    - Go back to task detail
    - Type a comment and click "Comment"
    - Confirm: comment appears with your name and timestamp?
    - Add a second comment
    - Confirm: count updates ("Comments (2)")?

[ ] 8. CHECK ACTIVITY FEED
    - Click "Activity" in sidebar
    - Confirm: your comments appear at the top?
    - Confirm: task lifecycle events (submitted, completed) visible?
    - Try the "Comments" filter — shows only comment events?

[ ] 9. CHECK NEEDS REVIEW
    - Click "Needs Review" in sidebar
    - Confirm: page renders (may show "All clear" if no pending items)
    - Tabs (All / Artifact approvals / Tool approvals) work?

[ ] 10. RUN DETAIL
     - From any completed task, click "Run details"
     - Confirm: heading shows task title (not UUID)?
     - Timeline shows lifecycle events?
     - Artifacts section links to output?

[ ] 11. SYSTEM HEALTH
     - Click "System Health" in sidebar
     - Service cards visible?
     - Agent Runtime section shows invocation counts?

[ ] 12. SESSION EXPIRY (if encountered)
     - If you see a yellow banner "Your session has expired"
     - Confirm: banner is visible for ~2 seconds before redirect
     - Log back in and continue

OVERALL IMPRESSION:
- The app felt like: [ ] a real product  [ ] internal tooling  [ ] somewhere between
- I knew where to find my results: [ ] Yes  [ ] Sometimes  [ ] No
- The output felt trustworthy: [ ] Yes  [ ] Somewhat  [ ] No
- Top friction moment: ___________
- Top "wow" moment: ___________
```

---

## 4. Feedback Template

```
MONAOS FEEDBACK REPORT

Reporter: ___________
Date: ___________
Category: [ ] Bug  [ ] UX Confusion  [ ] Missing Capability
          [ ] Collaboration Friction  [ ] Trust/Clarity Issue
          [ ] Performance/Loading

Severity: [ ] P0 - Blocks usage  [ ] P1 - Significant friction
          [ ] P2 - Minor annoyance  [ ] P3 - Suggestion

Route/Page: (e.g., /workspaces/.../tasks/new, /artifacts/...)

Steps to reproduce:
1.
2.
3.

Expected behavior:


Actual behavior:


Screenshot: (attach or describe)

Additional notes:

```

---

## 5. Caveats to Communicate

Tell testers these things **before they start**:

1. **Model provider**: The Claude Bridge service must be running on the host machine for AI-generated outputs. If tasks fail immediately, check with the system operator.

2. **Task completion time**: Tasks typically complete in 10–30 seconds. If a task shows "failed", it may be a provider connectivity issue, not a product bug. Use the "Retry Task" button.

3. **Session timeout**: Your login session may expire after a period of inactivity. You'll see a yellow banner "Your session has expired" before being redirected to login. Your data is not lost — just log back in.

4. **Activity feed**: The default "All" view shows high-level events. Use the category dropdown (Tasks, Comments, Runs) for focused views.

5. **Table rendering**: Markdown tables in artifact previews render as formatted grids. Use the "Rendered/Raw" toggle to switch between formatted and source views.

6. **System Health page**: This page (/health) is primarily for operators. The data may show stale timestamps — this is expected in the local test environment.

7. **Known cosmetic items** (not bugs):
   - Artifact type shows "model_output" — will be friendlier in next polish
   - Run detail shows "Attempt #" without the number
   - Some UUID-based links appear in artifact Details section

---

## 6. Feedback Processing Plan

After the first 3–5 testers complete the checklist, group feedback into:

| Category | Action |
|----------|--------|
| **Bug** | Fix immediately if P0/P1, queue if P2 |
| **UX Confusion** | Batch into next polish round |
| **Polish Request** | Evaluate ROI, defer unless multiple testers report same issue |

Do not plan the next batch until real feedback is collected.

---

## 7. Polish Watch List

These are candidates only — prioritize based on tester feedback:

1. "Attempt #" display — show actual attempt number on run detail
2. Friendlier artifact type labels — "model_output" → "AI-generated document"
3. Artifact Details section — show task/run titles instead of UUID links
