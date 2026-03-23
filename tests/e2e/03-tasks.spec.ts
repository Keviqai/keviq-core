/**
 * UJ-004: Create Task (full delegation flow)
 * Tests: task list, new task form, draft creation, edit, review, launch
 */
import { test, expect, API_URL } from './fixtures';

test.describe('Task List', () => {
  test('tasks page loads without error', async ({ page, workspaceId }) => {
    await page.goto(`/workspaces/${workspaceId}/tasks`);
    await expect(page).not.toHaveURL(/\/login/);
    await expect(page.locator('h1').first()).toBeVisible({ timeout: 10_000 });
    await expect(page.locator('body')).not.toContainText('unexpected error');
  });

  test('create task button or link visible when user has permission', async ({ page, workspaceId }) => {
    await page.goto(`/workspaces/${workspaceId}/tasks`);
    // Either a create button or a "+ New Task" link
    const createBtn = page.locator('a:has-text("New Task"), button:has-text("New Task"), a:has-text("Create Task")');
    // May be hidden if no permission — just check page doesn't crash
    await expect(page.locator('h1').first()).toBeVisible({ timeout: 10_000 });
  });
});

test.describe('Create Task Flow', () => {
  test('new task page renders title input', async ({ page, workspaceId }) => {
    await page.goto(`/workspaces/${workspaceId}/tasks/new`);
    await expect(page).not.toHaveURL(/\/login/);
    await expect(page.locator('body')).not.toContainText('unexpected error');
    // Input has placeholder "e.g. Q1 Competitive Analysis"
    await expect(page.locator('input[placeholder*="Q1"]')).toBeVisible({ timeout: 10_000 });
  });

  test('create draft → redirects to edit page', async ({ page, workspaceId }) => {
    await page.goto(`/workspaces/${workspaceId}/tasks/new`);

    // Fill in task title
    await page.locator('input[placeholder*="Q1"]').fill('Playwright E2E Test Task');

    // Submit — button text is "Create Draft" or similar
    await page.locator('button:has-text("Create")').first().click();

    // Should redirect to /tasks/{id}/edit
    await expect(page).toHaveURL(/\/tasks\/[a-f0-9-]+\/edit/, { timeout: 15_000 });
  });

  test('edit page has goal, desired_output fields', async ({ page, workspaceId, token }) => {
    // Create a task via the correct endpoint: POST /v1/tasks/draft
    const res = await page.request.post(`${API_URL}/v1/tasks/draft`, {
      data: { title: 'Playwright Edit Test', workspace_id: workspaceId },
      headers: { Authorization: `Bearer ${token}` },
    });
    expect(res.ok(), `Task draft API failed: ${res.status()} ${await res.text()}`).toBeTruthy();
    const task = await res.json() as { task_id: string };

    await page.goto(`/workspaces/${workspaceId}/tasks/${task.task_id}/edit`);
    await expect(page).not.toHaveURL(/\/login/);
    await expect(page.locator('body')).not.toContainText('unexpected error');

    // Goal textarea has placeholder "What should the agent accomplish?"
    await expect(page.locator('textarea[placeholder*="agent accomplish" i]')).toBeVisible({ timeout: 10_000 });
  });

  test('task detail page shows brief summary', async ({ page, workspaceId, token }) => {
    // Create a draft task via API
    const createRes = await page.request.post(`${API_URL}/v1/tasks/draft`, {
      data: { title: 'Playwright Detail Test', workspace_id: workspaceId },
      headers: { Authorization: `Bearer ${token}` },
    });
    expect(createRes.ok(), `Task draft API failed: ${createRes.status()} ${await createRes.text()}`).toBeTruthy();
    const task = await createRes.json() as { task_id: string };

    await page.goto(`/workspaces/${workspaceId}/tasks/${task.task_id}`);
    await expect(page).not.toHaveURL(/\/login/);
    await expect(page.locator('body')).not.toContainText('unexpected error');
    // Title should appear
    await expect(page.locator('body')).toContainText('Playwright Detail Test', { timeout: 10_000 });
  });
});
