'use client';

import { useQuery } from '@tanstack/react-query';
import { createRunsApi } from '@keviq/api-client';
import { apiClient } from '../api';
import { queryKeys } from '../query-keys';

const runsApi = createRunsApi(apiClient);

export function useRunsByTask(workspaceId: string, taskId: string) {
  return useQuery({
    queryKey: queryKeys.runs.listByTask(taskId),
    queryFn: () => runsApi.listByTask(workspaceId, taskId),
    enabled: !!workspaceId && !!taskId,
  });
}

export function useRun(runId: string) {
  return useQuery({
    queryKey: queryKeys.runs.detail(runId),
    queryFn: () => runsApi.get(runId),
    enabled: !!runId,
  });
}
