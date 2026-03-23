'use client';

import { useQuery } from '@tanstack/react-query';
import { createWorkspacesApi } from '@keviq/api-client';
import { apiClient } from '../api';
import { queryKeys } from '../query-keys';

const workspacesApi = createWorkspacesApi(apiClient);

export function useWorkspaces() {
  return useQuery({
    queryKey: queryKeys.workspaces.list,
    queryFn: () => workspacesApi.list(),
  });
}
