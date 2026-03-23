import type { ApiClient } from './client';
import type { Run } from '@keviq/domain-types';

export interface RunsApi {
  listByTask: (workspaceId: string, taskId: string) => Promise<{ items: Run[]; count: number }>;
  get: (runId: string) => Promise<Run>;
}

export function createRunsApi(client: ApiClient): RunsApi {
  return {
    listByTask: (workspaceId, taskId) =>
      client.get(`/v1/workspaces/${encodeURIComponent(workspaceId)}/tasks/${encodeURIComponent(taskId)}/runs`),
    get: (runId) => client.get(`/v1/runs/${encodeURIComponent(runId)}`),
  };
}
