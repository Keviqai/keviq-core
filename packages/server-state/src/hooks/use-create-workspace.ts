'use client';

import { useMutation, useQueryClient } from '@tanstack/react-query';
import { createWorkspacesApi } from '@keviq/api-client';
import type { Workspace } from '@keviq/domain-types';
import { apiClient } from '../api';
import { queryKeys } from '../query-keys';

const workspacesApi = createWorkspacesApi(apiClient);

export function useCreateWorkspace() {
  const qc = useQueryClient();
  return useMutation<Workspace, Error, { slug: string; displayName: string }>({
    mutationFn: ({ slug, displayName }) =>
      workspacesApi.create(slug, displayName),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: queryKeys.workspaces.list });
      qc.invalidateQueries({ queryKey: queryKeys.auth.me });
    },
  });
}
