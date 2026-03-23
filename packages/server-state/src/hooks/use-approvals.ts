'use client';

import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { createApprovalsApi } from '@keviq/api-client';
import type { DecideApprovalRequest, CreateApprovalRequest } from '@keviq/api-client';
import { apiClient } from '../api';
import { queryKeys } from '../query-keys';

const approvalsApi = createApprovalsApi(apiClient);

export function useApprovalList(workspaceId: string, decision?: string, reviewerId?: string) {
  return useQuery({
    queryKey: queryKeys.approvals.list(workspaceId, decision, reviewerId),
    queryFn: () => approvalsApi.list(workspaceId, decision, reviewerId),
    enabled: !!workspaceId,
    staleTime: 10_000,
  });
}

export function useApproval(workspaceId: string, approvalId: string) {
  return useQuery({
    queryKey: queryKeys.approvals.detail(workspaceId, approvalId),
    queryFn: () => approvalsApi.get(workspaceId, approvalId),
    enabled: !!workspaceId && !!approvalId,
    staleTime: 5_000,
  });
}

export function usePendingApprovalCount(workspaceId: string) {
  return useQuery({
    queryKey: queryKeys.approvals.count(workspaceId),
    queryFn: () => approvalsApi.countPending(workspaceId),
    enabled: !!workspaceId,
    staleTime: 30_000,
  });
}

export function useDecideApproval() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (vars: { workspaceId: string; approvalId: string; req: DecideApprovalRequest }) =>
      approvalsApi.decide(vars.workspaceId, vars.approvalId, vars.req),
    onSuccess: (_data, variables) => {
      // Broad invalidation to cover all filtered list variants
      qc.invalidateQueries({ queryKey: ['approvals'] });
      qc.invalidateQueries({ queryKey: queryKeys.approvals.detail(variables.workspaceId, variables.approvalId) });
    },
  });
}

export function useCreateApproval() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (vars: { workspaceId: string; req: CreateApprovalRequest }) =>
      approvalsApi.create(vars.workspaceId, vars.req),
    onSuccess: (_data, variables) => {
      qc.invalidateQueries({ queryKey: ['approvals'] });
      qc.invalidateQueries({ queryKey: queryKeys.approvals.count(variables.workspaceId) });
    },
  });
}
