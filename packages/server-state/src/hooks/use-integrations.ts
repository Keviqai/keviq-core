'use client';

import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { createIntegrationsApi } from '@keviq/api-client';
import type { CreateIntegrationRequest, UpdateIntegrationRequest } from '@keviq/api-client';
import { apiClient } from '../api';
import { queryKeys } from '../query-keys';

const integrationsApi = createIntegrationsApi(apiClient);

export function useIntegrations(workspaceId: string) {
  return useQuery({
    queryKey: queryKeys.integrations.list(workspaceId),
    queryFn: () => integrationsApi.list(workspaceId),
    enabled: !!workspaceId,
    staleTime: 15_000,
  });
}

export function useCreateIntegration() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (vars: { workspaceId: string; req: CreateIntegrationRequest }) =>
      integrationsApi.create(vars.workspaceId, vars.req),
    onSuccess: (_data, variables) => {
      qc.invalidateQueries({ queryKey: queryKeys.integrations.list(variables.workspaceId) });
    },
  });
}

export function useUpdateIntegration() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (vars: { workspaceId: string; integrationId: string; req: UpdateIntegrationRequest }) =>
      integrationsApi.update(vars.workspaceId, vars.integrationId, vars.req),
    onSuccess: (_data, variables) => {
      qc.invalidateQueries({ queryKey: queryKeys.integrations.list(variables.workspaceId) });
    },
  });
}

export function useDeleteIntegration() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (vars: { workspaceId: string; integrationId: string }) =>
      integrationsApi.remove(vars.workspaceId, vars.integrationId),
    onSuccess: (_data, variables) => {
      qc.invalidateQueries({ queryKey: queryKeys.integrations.list(variables.workspaceId) });
    },
  });
}

export function useToggleIntegration() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (vars: { workspaceId: string; integrationId: string }) =>
      integrationsApi.toggle(vars.workspaceId, vars.integrationId),
    onSuccess: (_data, variables) => {
      qc.invalidateQueries({ queryKey: queryKeys.integrations.list(variables.workspaceId) });
    },
  });
}
