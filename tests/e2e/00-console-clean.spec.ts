/**
 * Console-clean gate
 *
 * Verifies the main pages have no JS runtime errors and no unexpected
 * network 4xx/5xx responses. A pass here means the page is genuinely clean,
 * not just "renders something".
 *
 * Allowlisted patterns (known acceptable noise):
 *   - /v1/notifications/* — notification-service not running in minimal stack
 *   - /_next/image        — Next.js image optimisation needs external image source
 *   - /v1/auth/refresh    — token refresh race on first load is acceptable
 */
import { test, expect, type Page } from './fixtures';

// ── Allowlists ──────────────────────────────────────────────────────────────

const ALLOWED_NETWORK_ERRORS: RegExp[] = [
  /\/v1\/notifications/,
  /\/_next\/image/,
  /\/v1\/auth\/refresh/,
];

const ALLOWED_JS_ERRORS: RegExp[] = [
  /Download the React DevTools/,
];

function isAllowed(url: string, patterns: RegExp[]): boolean {
  return patterns.some((re) => re.test(url));
}

// ── Monitor helper ──────────────────────────────────────────────────────────

function attachMonitors(page: Page) {
  const networkErrors: { url: string; status: number }[] = [];
  const jsErrors: string[] = [];

  page.on('response', (res) => {
    if (res.status() >= 400 && !isAllowed(res.url(), ALLOWED_NETWORK_ERRORS)) {
      networkErrors.push({ url: res.url(), status: res.status() });
    }
  });

  page.on('pageerror', (err) => {
    if (!isAllowed(err.message, ALLOWED_JS_ERRORS)) {
      jsErrors.push(err.message);
    }
  });

  return { networkErrors, jsErrors };
}

function assertClean(
  networkErrors: { url: string; status: number }[],
  jsErrors: string[],
  page: string,
) {
  expect(
    jsErrors,
    `JS errors on ${page}:\n${jsErrors.join('\n')}`,
  ).toHaveLength(0);

  expect(
    networkErrors,
    `Network errors on ${page}:\n${networkErrors.map((e) => `  ${e.status} ${e.url}`).join('\n')}`,
  ).toHaveLength(0);
}

// ── Tests ────────────────────────────────────────────────────────────────────

test.describe('Console-clean gate — authenticated pages', () => {
  test('workspace overview — no JS errors, no unexpected 4xx', async ({ page, workspaceId }) => {
    const { networkErrors, jsErrors } = attachMonitors(page);
    await page.goto(`/workspaces/${workspaceId}`);
    await page.waitForLoadState('networkidle');
    assertClean(networkErrors, jsErrors, 'workspace overview');
  });

  test('task list — no JS errors, no unexpected 4xx', async ({ page, workspaceId }) => {
    const { networkErrors, jsErrors } = attachMonitors(page);
    await page.goto(`/workspaces/${workspaceId}/tasks`);
    await page.waitForLoadState('networkidle');
    assertClean(networkErrors, jsErrors, 'task list');
  });

  test('artifacts page — no JS errors, no unexpected 4xx', async ({ page, workspaceId }) => {
    const { networkErrors, jsErrors } = attachMonitors(page);
    await page.goto(`/workspaces/${workspaceId}/artifacts`);
    await page.waitForLoadState('networkidle');
    assertClean(networkErrors, jsErrors, 'artifacts page');
  });

  test('approvals page — no JS errors, no unexpected 4xx', async ({ page, workspaceId }) => {
    const { networkErrors, jsErrors } = attachMonitors(page);
    await page.goto(`/workspaces/${workspaceId}/approvals`);
    await page.waitForLoadState('networkidle');
    assertClean(networkErrors, jsErrors, 'approvals page');
  });

  test('new task page — no JS errors, no unexpected 4xx', async ({ page, workspaceId }) => {
    const { networkErrors, jsErrors } = attachMonitors(page);
    await page.goto(`/workspaces/${workspaceId}/tasks/new`);
    await page.waitForLoadState('networkidle');
    assertClean(networkErrors, jsErrors, 'new task page');
  });
});

test.describe('Console-clean gate — login page', () => {
  test('login page — no JS errors', async ({ page }) => {
    await page.context().clearCookies();
    const { networkErrors, jsErrors } = attachMonitors(page);
    await page.goto('/login');
    await page.waitForLoadState('networkidle');
    assertClean(networkErrors, jsErrors, 'login page');
  });
});
