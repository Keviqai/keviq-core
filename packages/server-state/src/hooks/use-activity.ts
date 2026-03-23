'use client';

import { useQuery } from '@tanstack/react-query';
import { createActivityApi } from '@keviq/api-client';
import type { ActivityQueryParams } from '@keviq/api-client';
import { apiClient } from '../api';
import { queryKeys } from '../query-keys';

const activityApi = createActivityApi(apiClient);

export function useActivity(workspaceId: string, params?: ActivityQueryParams) {
  return useQuery({
    queryKey: queryKeys.activity.list(workspaceId, params as Record<string, unknown> | undefined),
    queryFn: () => activityApi.list(workspaceId, params),
    enabled: !!workspaceId,
    staleTime: 10_000,
  });
}
