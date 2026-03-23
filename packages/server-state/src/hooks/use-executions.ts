'use client';

import { useQuery } from '@tanstack/react-query';
import { createExecutionsApi } from '@keviq/api-client';
import { apiClient } from '../api';
import { queryKeys } from '../query-keys';

const executionsApi = createExecutionsApi(apiClient);

export function useToolExecution(executionId: string | null) {
  return useQuery({
    queryKey: queryKeys.executions.detail(executionId ?? ''),
    queryFn: () => executionsApi.getExecution(executionId!),
    enabled: !!executionId,
    staleTime: 60_000, // Execution details rarely change once completed
  });
}

export function useSandboxDetail(sandboxId: string | null) {
  return useQuery({
    queryKey: queryKeys.sandboxes.detail(sandboxId ?? ''),
    queryFn: () => executionsApi.getSandbox(sandboxId!),
    enabled: !!sandboxId,
    staleTime: 60_000,
  });
}
