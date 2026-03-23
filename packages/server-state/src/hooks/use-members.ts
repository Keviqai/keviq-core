'use client';

import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { createMembersApi } from '@keviq/api-client';
import type { InviteMemberRequest, UpdateMemberRoleRequest } from '@keviq/api-client';
import { apiClient } from '../api';
import { queryKeys } from '../query-keys';

const membersApi = createMembersApi(apiClient);

export function useMembers(workspaceId: string) {
  return useQuery({
    queryKey: queryKeys.members.list(workspaceId),
    queryFn: () => membersApi.list(workspaceId),
    enabled: !!workspaceId,
  });
}

export function useInviteMember(workspaceId: string) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (req: InviteMemberRequest) => membersApi.invite(workspaceId, req),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: queryKeys.members.list(workspaceId) });
    },
  });
}

export function useUpdateMemberRole(workspaceId: string) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (params: { memberUserId: string; role: string }) =>
      membersApi.updateRole(workspaceId, params.memberUserId, { role: params.role }),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: queryKeys.members.list(workspaceId) });
    },
  });
}

export function useRemoveMember(workspaceId: string) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (memberUserId: string) => membersApi.remove(workspaceId, memberUserId),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: queryKeys.members.list(workspaceId) });
    },
  });
}
