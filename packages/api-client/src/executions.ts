import type { ApiClient } from './client';
import type { ToolExecutionDetail, SandboxDetail } from '@keviq/domain-types';

export interface ExecutionsApi {
  getExecution: (executionId: string) => Promise<ToolExecutionDetail>;
  getSandbox: (sandboxId: string) => Promise<SandboxDetail>;
}

export function createExecutionsApi(client: ApiClient): ExecutionsApi {
  return {
    getExecution: (executionId) =>
      client.get(`/v1/tool-executions/${encodeURIComponent(executionId)}`),
    getSandbox: (sandboxId) =>
      client.get(`/v1/sandboxes/${encodeURIComponent(sandboxId)}`),
  };
}
