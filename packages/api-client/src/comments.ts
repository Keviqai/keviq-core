import type { ApiClient } from './client';
import type { TaskComment } from '@keviq/domain-types';

export interface CommentsApi {
  listTaskComments: (workspaceId: string, taskId: string) => Promise<{ items: TaskComment[]; count: number }>;
  createTaskComment: (workspaceId: string, taskId: string, body: string) => Promise<TaskComment>;
}

export function createCommentsApi(client: ApiClient): CommentsApi {
  return {
    listTaskComments: (workspaceId, taskId) =>
      client.get(`/v1/workspaces/${encodeURIComponent(workspaceId)}/tasks/${encodeURIComponent(taskId)}/comments`),
    createTaskComment: (workspaceId, taskId, body) =>
      client.post(`/v1/workspaces/${encodeURIComponent(workspaceId)}/tasks/${encodeURIComponent(taskId)}/comments`, { body }),
  };
}
