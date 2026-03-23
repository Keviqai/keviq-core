'use client';

import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { createPoliciesApi } from '@keviq/api-client';
import type { CreatePolicyRequest, UpdatePolicyRequest } from '@keviq/api-client';
import { apiClient } from '../api';
import { queryKeys } from '../query-keys';

const policiesApi = createPoliciesApi(apiClient);

export function usePolicies(workspaceId: string) {
  return useQuery({
    queryKey: queryKeys.policies.list(workspaceId),
    queryFn: () => policiesApi.list(workspaceId),
    enabled: !!workspaceId,
    staleTime: 15_000,
  });
}

export function useCreatePolicy() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (vars: { workspaceId: string; req: CreatePolicyRequest }) =>
      policiesApi.create(vars.workspaceId, vars.req),
    onSuccess: (_data, variables) => {
      qc.invalidateQueries({ queryKey: queryKeys.policies.list(variables.workspaceId) });
    },
  });
}

export function useUpdatePolicy() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (vars: { workspaceId: string; policyId: string; req: UpdatePolicyRequest }) =>
      policiesApi.update(vars.workspaceId, vars.policyId, vars.req),
    onSuccess: (_data, variables) => {
      qc.invalidateQueries({ queryKey: queryKeys.policies.list(variables.workspaceId) });
    },
  });
}
