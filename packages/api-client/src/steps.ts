import type { ApiClient } from './client';
import type { Step } from '@keviq/domain-types';

export interface StepsApi {
  listByRun: (runId: string) => Promise<{ items: Step[]; count: number }>;
}

export function createStepsApi(client: ApiClient): StepsApi {
  return {
    listByRun: (runId) =>
      client.get(`/v1/runs/${encodeURIComponent(runId)}/steps`),
  };
}
