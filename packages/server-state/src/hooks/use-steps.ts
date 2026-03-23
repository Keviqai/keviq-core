'use client';

import { useQuery } from '@tanstack/react-query';
import { createStepsApi } from '@keviq/api-client';
import { apiClient } from '../api';
import { queryKeys } from '../query-keys';

const stepsApi = createStepsApi(apiClient);

export function useStepsByRun(runId: string) {
  return useQuery({
    queryKey: queryKeys.steps.listByRun(runId),
    queryFn: () => stepsApi.listByRun(runId),
    enabled: !!runId,
  });
}
