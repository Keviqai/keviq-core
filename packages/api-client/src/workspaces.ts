import type { ApiClient } from './client';
import type { Workspace } from '@keviq/domain-types';

export interface WorkspacesApi {
  list: () => Promise<Workspace[]>;
  get: (workspaceId: string) => Promise<Workspace>;
  create: (slug: string, displayName: string) => Promise<Workspace>;
}

export function createWorkspacesApi(client: ApiClient): WorkspacesApi {
  return {
    list: () => client.get('/v1/workspaces'),
    get: (workspaceId) => client.get(`/v1/workspaces/${encodeURIComponent(workspaceId)}`),
    create: (slug, displayName) =>
      client.post('/v1/workspaces', { slug, display_name: displayName }),
  };
}
