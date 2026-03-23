import type { ApiClient } from './client';
import type { AuthSession, User, Workspace } from '@keviq/domain-types';

export interface AuthApi {
  me: () => Promise<{ user: User; workspaces: Workspace[] }>;
  login: (email: string, password: string) => Promise<AuthSession>;
  register: (email: string, displayName: string, password: string) => Promise<AuthSession>;
  logout: () => Promise<void>;
}

export function createAuthApi(client: ApiClient): AuthApi {
  return {
    me: () => client.get('/v1/auth/me'),
    login: (email, password) => client.post('/v1/auth/login', { email, password }),
    register: (email, displayName, password) =>
      client.post('/v1/auth/register', { email, display_name: displayName, password }),
    logout: () => client.post('/v1/auth/logout'),
  };
}
