'use client';

import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { createSecretsApi } from '@keviq/api-client';
import type { CreateSecretRequest } from '@keviq/api-client';
import { apiClient } from '../api';
import { queryKeys } from '../query-keys';

const secretsApi = createSecretsApi(apiClient);

export function useSecrets(workspaceId: string) {
  return useQuery({
    queryKey: queryKeys.secrets.list(workspaceId),
    queryFn: () => secretsApi.list(workspaceId),
    enabled: !!workspaceId,
    staleTime: 15_000,
  });
}

export function useCreateSecret() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (vars: { workspaceId: string; req: CreateSecretRequest }) =>
      secretsApi.create(vars.workspaceId, vars.req),
    onSuccess: (_data, variables) => {
      qc.invalidateQueries({ queryKey: queryKeys.secrets.list(variables.workspaceId) });
    },
  });
}

export function useDeleteSecret() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (vars: { workspaceId: string; secretId: string }) =>
      secretsApi.remove(vars.workspaceId, vars.secretId),
    onSuccess: (_data, variables) => {
      qc.invalidateQueries({ queryKey: queryKeys.secrets.list(variables.workspaceId) });
    },
  });
}
