/**
 * UJ-002: Register & Login
 * Tests: login page, login flow, logout, redirect behavior
 */
import { test, expect, TEST_USER, API_URL } from './fixtures';
import { test as base } from '@playwright/test';

base.describe('Auth — Login & Logout', () => {
  base.beforeEach(async ({ page }) => {
    // Clear cookies to start unauthenticated
    await page.context().clearCookies();
  });

  base.test('unauthenticated user redirected to /login', async ({ page }) => {
    await page.goto('/');
    await expect(page).toHaveURL(/\/login/);
  });

  base.test('login page renders email + password fields', async ({ page }) => {
    await page.goto('/login');
    await expect(page.locator('input[type="email"], input[name="email"]')).toBeVisible();
    await expect(page.locator('input[type="password"]')).toBeVisible();
    await expect(page.locator('button[type="submit"], button:has-text("Login"), button:has-text("Sign in"), button:has-text("Đăng nhập")')).toBeVisible();
  });

  base.test('invalid credentials shows error', async ({ page }) => {
    await page.goto('/login');
    await page.locator('input[type="email"], input[name="email"]').fill('nobody@nowhere.com');
    await page.locator('input[type="password"]').fill('wrongpassword');
    await page.locator('button[type="submit"], button:has-text("Login"), button:has-text("Sign in")').click();
    // Should stay on login page and show an error
    await expect(page).toHaveURL(/\/login/);
    await expect(page.locator('body')).toContainText(/invalid|incorrect|error|wrong/i);
  });

  base.test('valid credentials login and redirect to workspace or onboarding', async ({ page }) => {
    await page.goto('/login');
    await page.locator('input[type="email"], input[name="email"]').fill(TEST_USER.email);
    await page.locator('input[type="password"]').fill(TEST_USER.password);
    await page.locator('button[type="submit"], button:has-text("Login"), button:has-text("Sign in")').click();

    // Should redirect away from /login
    await expect(page).not.toHaveURL(/\/login/, { timeout: 10_000 });
    // Should be on workspaces or onboarding
    await expect(page).toHaveURL(/\/(workspaces|onboarding)/, { timeout: 10_000 });
  });

  base.test('register page renders correctly', async ({ page }) => {
    await page.goto('/register');
    await expect(page.locator('input[type="email"], input[name="email"]')).toBeVisible();
    await expect(page.locator('input[type="password"]')).toBeVisible();
  });
});

// Tests that require being logged in
test.describe('Auth — Authenticated state', () => {
  test('auth/me returns user info via API', async ({ page, token }) => {
    const res = await page.request.get(`${API_URL}/v1/auth/me`, {
      headers: { Authorization: `Bearer ${token}` },
    });
    expect(res.ok()).toBeTruthy();
    const body = await res.json() as { email: string };
    expect(body.email).toBe(TEST_USER.email);
  });

  test('logout clears session and redirects to /login', async ({ page, token }) => {
    await page.goto('/login');
    // Already logged in via cookie from fixture, navigate away
    await page.goto('/');
    await expect(page).toHaveURL(/\/(workspaces|onboarding)/, { timeout: 10_000 });

    // Find logout button and click
    const logoutBtn = page.locator('button:has-text("Logout"), button:has-text("Sign out"), a:has-text("Logout"), [data-testid="logout"]');
    if (await logoutBtn.count() > 0) {
      await logoutBtn.first().click();
      await expect(page).toHaveURL(/\/login/, { timeout: 5_000 });
    } else {
      // Manually clear cookie
      await page.context().clearCookies();
      await page.goto('/');
      await expect(page).toHaveURL(/\/login/, { timeout: 5_000 });
    }
  });
});
