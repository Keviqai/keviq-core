import type { ApiClient } from './client';
import type { WorkspaceMember } from '@keviq/domain-types';

export interface InviteMemberRequest {
  user_id: string;
  role: string;
}

export interface UpdateMemberRoleRequest {
  role: string;
}

export interface MembersApi {
  list: (workspaceId: string) => Promise<WorkspaceMember[]>;
  invite: (workspaceId: string, req: InviteMemberRequest) => Promise<WorkspaceMember>;
  updateRole: (workspaceId: string, memberUserId: string, req: UpdateMemberRoleRequest) => Promise<WorkspaceMember>;
  remove: (workspaceId: string, memberUserId: string) => Promise<void>;
}

export function createMembersApi(client: ApiClient): MembersApi {
  return {
    list: (workspaceId) =>
      client.get(`/v1/workspaces/${encodeURIComponent(workspaceId)}/members`),
    invite: (workspaceId, req) =>
      client.post(`/v1/workspaces/${encodeURIComponent(workspaceId)}/members`, req),
    updateRole: (workspaceId, memberUserId, req) =>
      client.patch(
        `/v1/workspaces/${encodeURIComponent(workspaceId)}/members/${encodeURIComponent(memberUserId)}`,
        req,
      ),
    remove: (workspaceId, memberUserId) =>
      client.delete(
        `/v1/workspaces/${encodeURIComponent(workspaceId)}/members/${encodeURIComponent(memberUserId)}`,
      ),
  };
}
