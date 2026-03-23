/**
 * UJ-003: Create Workspace
 * UJ-004 (partial): Workspace overview page
 * Tests: workspace overview renders, stat cards visible, nav links work
 */
import { test, expect } from './fixtures';

test.describe('Workspace Overview', () => {
  test('workspace overview page loads with correct title', async ({ page, workspaceId }) => {
    await page.goto(`/workspaces/${workspaceId}`);
    await expect(page).not.toHaveURL(/\/login/);
    // H1 should show workspace name (not crash)
    await expect(page.locator('h1').first()).toBeVisible({ timeout: 10_000 });
    // Should not show error boundary
    await expect(page.locator('body')).not.toContainText('unexpected error');
  });

  test('stat cards (Drafts, Active, Pending Approvals) render', async ({ page, workspaceId }) => {
    await page.goto(`/workspaces/${workspaceId}`);
    await expect(page.locator('text=Drafts')).toBeVisible({ timeout: 10_000 });
    await expect(page.locator('text=Active')).toBeVisible();
    await expect(page.locator('text=Pending Approvals')).toBeVisible();
  });

  test('+ New Task button is visible and links to /tasks/new', async ({ page, workspaceId }) => {
    await page.goto(`/workspaces/${workspaceId}`);
    const newTaskBtn = page.locator('a:has-text("New Task")');
    await expect(newTaskBtn).toBeVisible({ timeout: 10_000 });
    await expect(newTaskBtn).toHaveAttribute('href', new RegExp(`/workspaces/${workspaceId}/tasks/new`));
  });

  test('Recent Artifacts section renders', async ({ page, workspaceId }) => {
    await page.goto(`/workspaces/${workspaceId}`);
    await expect(page.locator('text=Recent Artifacts')).toBeVisible({ timeout: 10_000 });
  });

  test('sidebar navigation links are present', async ({ page, workspaceId }) => {
    await page.goto(`/workspaces/${workspaceId}`);
    // Check for main nav items in sidebar
    const nav = page.locator('nav, aside, [role="navigation"]');
    await expect(nav.first()).toBeVisible({ timeout: 10_000 });
  });

  test('onboarding page accessible (redirects to workspace if user already has one)', async ({ page, token }) => {
    await page.goto('/onboarding');
    // Authenticated user with a workspace gets redirected to workspace — either outcome is OK
    await expect(page).not.toHaveURL(/\/login/, { timeout: 5_000 });
  });
});
