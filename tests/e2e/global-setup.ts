/**
 * Runs once before all tests.
 * Logs in via API, saves auth state to file so tests reuse the session.
 */
import { chromium, type FullConfig } from '@playwright/test';
import * as fs from 'fs';
import * as path from 'path';

const API_URL = 'http://localhost:8080';
const STATE_FILE = path.join(__dirname, '.auth-state.json');

export default async function globalSetup(_config: FullConfig) {
  const browser = await chromium.launch();
  const context = await browser.newContext();
  const page = await context.newPage();

  // Try login first; if user doesn't exist (clean boot), register then login.
  let loginRes = await page.request.post(`${API_URL}/v1/auth/login`, {
    data: { email: 'playwright@test.com', password: 'testpassword123' },
  });

  if (!loginRes.ok()) {
    console.log('Login failed — registering test user...');
    const regRes = await page.request.post(`${API_URL}/v1/auth/register`, {
      data: {
        email: 'playwright@test.com',
        password: 'testpassword123',
        display_name: 'Playwright Tester',
      },
    });
    if (!regRes.ok()) {
      throw new Error(`Global setup register failed: ${await regRes.text()}`);
    }
    // Login again after register
    loginRes = await page.request.post(`${API_URL}/v1/auth/login`, {
      data: { email: 'playwright@test.com', password: 'testpassword123' },
    });
    if (!loginRes.ok()) {
      throw new Error(`Global setup login after register failed: ${await loginRes.text()}`);
    }
  }
  const { access_token } = await loginRes.json() as { access_token: string };

  // Get or create workspace
  const wsRes = await page.request.get(`${API_URL}/v1/workspaces`, {
    headers: { Authorization: `Bearer ${access_token}` },
  });
  let workspaces = await wsRes.json() as { id: string; display_name: string }[];

  if (!workspaces.length) {
    console.log('No workspaces — creating test workspace...');
    const createWsRes = await page.request.post(`${API_URL}/v1/workspaces`, {
      data: {
        display_name: 'Playwright Test Workspace',
        slug: `pw-test-${Date.now()}`,
      },
      headers: { Authorization: `Bearer ${access_token}` },
    });
    if (!createWsRes.ok()) {
      throw new Error(`Global setup workspace creation failed: ${await createWsRes.text()}`);
    }
    const newWs = await createWsRes.json() as { id: string };
    workspaces = [{ id: newWs.id, display_name: 'Playwright Test Workspace' }];
  }

  const state = {
    token: access_token,
    workspaceId: workspaces[0]?.id ?? null,
  };

  fs.writeFileSync(STATE_FILE, JSON.stringify(state, null, 2));
  await browser.close();
}
