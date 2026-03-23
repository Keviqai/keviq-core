import type { ApiClient } from './client';
import type { Task } from '@keviq/domain-types';

export interface CreateTaskRequest {
  workspace_id: string;
  title: string;
  task_type: string;
  description?: string;
}

export interface CreateDraftRequest {
  workspace_id: string;
  title: string;
  task_type?: string;
  goal?: string;
  context?: string;
  constraints?: string;
  desired_output?: string;
  template_id?: string;
  agent_template_id?: string;
  risk_level?: string;
}

export interface CreateTaskResponse {
  task_id: string;
  status: string;
  links: { task: string };
}

export interface CancelTaskResponse {
  task_id: string;
  status: string;
  cancelled_runs: number;
  cancelled_steps: number;
}

export interface RetryTaskResponse {
  task_id: string;
  status: string;
}

export interface TasksApi {
  list: (workspaceId: string) => Promise<{ items: Task[]; count: number }>;
  get: (taskId: string) => Promise<Task>;
  create: (req: CreateTaskRequest) => Promise<CreateTaskResponse>;
  createDraft: (req: CreateDraftRequest) => Promise<Task>;
  updateBrief: (taskId: string, updates: Record<string, unknown>) => Promise<Task>;
  launch: (taskId: string) => Promise<CreateTaskResponse>;
  cancel: (taskId: string) => Promise<CancelTaskResponse>;
  retry: (taskId: string) => Promise<RetryTaskResponse>;
}

export function createTasksApi(client: ApiClient): TasksApi {
  return {
    list: (workspaceId) =>
      client.get(`/v1/tasks?workspace_id=${encodeURIComponent(workspaceId)}`),
    get: (taskId) => client.get(`/v1/tasks/${encodeURIComponent(taskId)}`),
    create: (req) => client.post('/v1/tasks', req),
    createDraft: (req) => client.post('/v1/tasks/draft', req),
    updateBrief: (taskId, updates) =>
      client.patch(`/v1/tasks/${encodeURIComponent(taskId)}`, updates),
    launch: (taskId) =>
      client.post(`/v1/tasks/${encodeURIComponent(taskId)}/launch`, {}),
    cancel: (taskId) =>
      client.post(`/v1/tasks/${encodeURIComponent(taskId)}/cancel`, {}),
    retry: (taskId) =>
      client.post(`/v1/tasks/${encodeURIComponent(taskId)}/retry`, {}),
  };
}
