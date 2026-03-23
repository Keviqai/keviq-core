/**
 * CVP-1: Full chained E2E journey.
 *
 * Proves the core Keviq Core value loop works end-to-end in a real browser:
 *   register → login → workspace → task → artifact → approval
 *
 * Uses a fresh user per run to avoid stale state.
 * Each step depends on the previous — chain breaks loudly on failure.
 */
import { test as base, expect } from '@playwright/test';

const API_URL = 'http://localhost:8080';
const RUN_ID = Date.now();

base.describe('Full Journey: Register → Approval', () => {
  // Chain state shared across steps via test.step()
  const state: {
    email: string;
    password: string;
    token: string;
    workspaceId: string;
    taskId: string;
    artifactId: string;
  } = {
    email: `journey-${RUN_ID}@test.com`,
    password: 'JourneyTest1234!',
    token: '',
    workspaceId: '',
    taskId: '',
    artifactId: '',
  };

  base.test('complete user journey', async ({ page }) => {
    // ── Step 1: Register ────────────────────────────────────
    await base.step('Register fresh user via API', async () => {
      const res = await page.request.post(`${API_URL}/v1/auth/register`, {
        data: {
          email: state.email,
          password: state.password,
          display_name: `Journey Tester ${RUN_ID}`,
        },
      });
      expect(res.ok(), `Register failed: ${res.status()}`).toBeTruthy();
      const body = await res.json() as { access_token: string };
      state.token = body.access_token;
      expect(state.token).toBeTruthy();
    });

    // ── Step 2: Login via browser ───────────────────────────
    await base.step('Login via browser UI', async () => {
      await page.goto('/login');
      await page.locator('input[type="email"], input[name="email"]').fill(state.email);
      await page.locator('input[type="password"]').fill(state.password);
      await page.locator('button[type="submit"]').click();

      // Should redirect away from /login
      await expect(page).not.toHaveURL(/\/login/, { timeout: 10_000 });
    });

    // ── Step 3: Create workspace ────────────────────────────
    await base.step('Create workspace via API', async () => {
      const res = await page.request.post(`${API_URL}/v1/workspaces`, {
        data: {
          display_name: `Journey WS ${RUN_ID}`,
          slug: `journey-ws-${RUN_ID}`,
        },
        headers: { Authorization: `Bearer ${state.token}` },
      });
      expect(res.ok(), `Workspace creation failed: ${res.status()}`).toBeTruthy();
      const body = await res.json() as { id: string };
      state.workspaceId = body.id;
      expect(state.workspaceId).toBeTruthy();
    });

    // ── Step 4: Navigate to workspace overview ──────────────
    await base.step('Navigate to workspace overview', async () => {
      // Set auth cookie for browser navigation
      await page.context().addCookies([{
        name: 'access_token',
        value: state.token,
        domain: 'localhost',
        path: '/',
        httpOnly: false,
        secure: false,
      }]);

      await page.goto(`/workspaces/${state.workspaceId}`);
      await expect(page).not.toHaveURL(/\/login/);
      await expect(page.locator('body')).not.toContainText('unexpected error');
      // Page should render without crash
      await expect(page.locator('body')).toBeVisible();
    });

    // ── Step 5: Create task draft + verify ───────────────────
    await base.step('Create task draft and verify in UI', async () => {
      const res = await page.request.post(`${API_URL}/v1/tasks/draft`, {
        data: {
          title: `Journey Task ${RUN_ID}`,
          workspace_id: state.workspaceId,
          task_type: 'custom',
        },
        headers: { Authorization: `Bearer ${state.token}` },
      });
      expect(res.ok(), `Task draft failed: ${res.status()}`).toBeTruthy();
      const body = await res.json() as { task_id: string };
      state.taskId = body.task_id;
      expect(state.taskId).toBeTruthy();

      // Navigate to task detail and verify title appears
      await page.goto(`/workspaces/${state.workspaceId}/tasks/${state.taskId}`);
      await expect(page.locator('body')).toContainText(`Journey Task ${RUN_ID}`, {
        timeout: 10_000,
      });
    });

    // ── Step 6: Upload artifact + verify ─────────────────────
    await base.step('Upload artifact and verify in UI', async () => {
      const res = await page.request.post(
        `${API_URL}/v1/workspaces/${state.workspaceId}/artifacts/upload`,
        {
          headers: { Authorization: `Bearer ${state.token}` },
          multipart: {
            file: {
              name: `journey-artifact-${RUN_ID}.txt`,
              mimeType: 'text/plain',
              buffer: Buffer.from(`Full journey test content — run ${RUN_ID}`),
            },
          },
        },
      );
      expect(res.ok(), `Artifact upload failed: ${res.status()}`).toBeTruthy();
      const body = await res.json() as { id: string };
      state.artifactId = body.id;
      expect(state.artifactId).toBeTruthy();

      // Navigate to artifact detail and verify name
      await page.goto(`/workspaces/${state.workspaceId}/artifacts/${state.artifactId}`);
      await expect(page.locator('body')).not.toContainText('unexpected error');
      await expect(page.locator('body')).toContainText(`journey-artifact-${RUN_ID}`, {
        timeout: 10_000,
      });
    });

    // ── Step 7: Request approval + verify ─────────────────────
    await base.step('Request approval and verify in approval center', async () => {
      const res = await page.request.post(
        `${API_URL}/v1/workspaces/${state.workspaceId}/approvals`,
        {
          data: {
            workspace_id: state.workspaceId,
            target_type: 'artifact',
            target_id: state.artifactId,
            prompt: `Please review journey artifact ${RUN_ID}`,
          },
          headers: { Authorization: `Bearer ${state.token}` },
        },
      );
      expect(res.ok(), `Approval creation failed: ${res.status()}`).toBeTruthy();

      // Navigate to approvals page and verify pending approval exists
      await page.goto(`/workspaces/${state.workspaceId}/approvals`);
      await expect(page.locator('body')).not.toContainText('unexpected error');
      // The approval prompt or "pending" should appear
      await expect(page.locator('body')).toContainText(/pending|review/i, {
        timeout: 10_000,
      });
    });
  });
});
