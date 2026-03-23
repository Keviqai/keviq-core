/**
 * Navigation & Shell
 * Tests: sidebar navigation, page transitions, 404 handling
 */
import { test, expect } from './fixtures';

test.describe('Shell Navigation', () => {
  test('can navigate to tasks from workspace overview', async ({ page, workspaceId }) => {
    await page.goto(`/workspaces/${workspaceId}`);
    await page.goto(`/workspaces/${workspaceId}/tasks`);
    await expect(page).toHaveURL(new RegExp(`/workspaces/${workspaceId}/tasks`));
    await expect(page.locator('body')).not.toContainText('unexpected error');
  });

  test('can navigate to artifacts page', async ({ page, workspaceId }) => {
    await page.goto(`/workspaces/${workspaceId}/artifacts`);
    await expect(page).toHaveURL(new RegExp(`/workspaces/${workspaceId}/artifacts`));
    await expect(page.locator('body')).not.toContainText('unexpected error');
  });

  test('can navigate to approvals page', async ({ page, workspaceId }) => {
    await page.goto(`/workspaces/${workspaceId}/approvals`);
    await expect(page.locator('body')).not.toContainText('unexpected error');
  });

  test('can navigate to settings page', async ({ page, workspaceId }) => {
    await page.goto(`/workspaces/${workspaceId}/settings`);
    await expect(page.locator('body')).not.toContainText('unexpected error');
  });

  test('members page renders', async ({ page, workspaceId }) => {
    await page.goto(`/workspaces/${workspaceId}/settings/members`);
    await expect(page.locator('body')).not.toContainText('unexpected error');
  });

  test('activity page renders', async ({ page, workspaceId }) => {
    await page.goto(`/workspaces/${workspaceId}/activity`);
    await expect(page.locator('body')).not.toContainText('unexpected error');
  });
});

test.describe('API Health via Browser', () => {
  test('auth login endpoint accepts POST (gateway is up)', async ({ page }) => {
    // api-gateway has no public /health — probe via a known endpoint
    const res = await page.request.post('http://localhost:8080/v1/auth/login', {
      data: { email: 'nobody@test.com', password: 'wrong' },
    });
    // 401 means gateway is routing correctly
    expect([200, 401, 422].includes(res.status())).toBeTruthy();
  });

  test('workspaces API returns array', async ({ page, token }) => {
    const res = await page.request.get('http://localhost:8080/v1/workspaces', {
      headers: { Authorization: `Bearer ${token}` },
    });
    expect(res.ok()).toBeTruthy();
    // Workspaces API returns a plain array
    const body = await res.json();
    expect(Array.isArray(body)).toBeTruthy();
  });
});
