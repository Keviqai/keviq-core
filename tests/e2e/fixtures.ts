import { test as base, expect, type Page } from '@playwright/test';
import * as fs from 'fs';
import * as path from 'path';

export const TEST_USER = {
  email: 'playwright@test.com',
  password: 'testpassword123',
  displayName: 'Playwright Tester',
};

export const BASE_URL = 'http://localhost:3000';
export const API_URL = 'http://localhost:8080';

const STATE_FILE = path.join(__dirname, '.auth-state.json');

function loadState(): { token: string; workspaceId: string } {
  const raw = fs.readFileSync(STATE_FILE, 'utf-8');
  return JSON.parse(raw);
}

/**
 * Set the saved access token as a cookie so Next.js picks it up.
 */
export async function setAuthCookie(page: Page, token: string) {
  await page.context().addCookies([{
    name: 'access_token',
    value: token,
    domain: 'localhost',
    path: '/',
    httpOnly: false,
    secure: false,
  }]);
}

// Extended test fixture with pre-loaded token + workspaceId from global setup
type Fixtures = {
  token: string;
  workspaceId: string;
};

export const test = base.extend<Fixtures>({
  token: async ({ page }, use) => {
    const { token } = loadState();
    await setAuthCookie(page, token);
    await use(token);
  },
  workspaceId: async ({ page, token }, use) => {
    const { workspaceId } = loadState();
    if (!workspaceId) {
      throw new Error('No workspace found for test user. Run global setup first.');
    }
    await use(workspaceId);
  },
});

export { expect };
