import type { ApiClient } from './client';
import type { ApprovalRequest } from '@keviq/domain-types';

export interface DecideApprovalRequest {
  decision: 'approve' | 'reject' | 'override' | 'cancel';
  comment?: string;
  /** Required when decision is 'override' — synthetic tool result content */
  override_output?: string;
}

export interface DecideApprovalResponse {
  approval_id: string;
  decision: string;
  status: string;
}

export interface CreateApprovalRequest {
  target_id: string;
  prompt: string;
  reviewer_id?: string;
}

export interface ApprovalsApi {
  list: (workspaceId: string, decision?: string, reviewerId?: string) => Promise<{ items: ApprovalRequest[]; count: number }>;
  get: (workspaceId: string, approvalId: string) => Promise<ApprovalRequest>;
  decide: (workspaceId: string, approvalId: string, req: DecideApprovalRequest) => Promise<DecideApprovalResponse>;
  countPending: (workspaceId: string) => Promise<{ pending_count: number }>;
  create: (workspaceId: string, req: CreateApprovalRequest) => Promise<ApprovalRequest>;
}

export function createApprovalsApi(client: ApiClient): ApprovalsApi {
  return {
    list: (workspaceId, decision, reviewerId) => {
      const params = new URLSearchParams();
      if (decision) params.set('decision', decision);
      if (reviewerId) params.set('reviewer_id', reviewerId);
      const qs = params.toString();
      const url = `/v1/workspaces/${encodeURIComponent(workspaceId)}/approvals${qs ? `?${qs}` : ''}`;
      return client.get(url);
    },
    get: (workspaceId, approvalId) =>
      client.get(`/v1/workspaces/${encodeURIComponent(workspaceId)}/approvals/${encodeURIComponent(approvalId)}`),
    decide: (workspaceId, approvalId, req) =>
      client.post(`/v1/workspaces/${encodeURIComponent(workspaceId)}/approvals/${encodeURIComponent(approvalId)}/decide`, req),
    countPending: (workspaceId) =>
      client.get(`/v1/workspaces/${encodeURIComponent(workspaceId)}/approvals/count`),
    create: (workspaceId, req) =>
      client.post(`/v1/workspaces/${encodeURIComponent(workspaceId)}/approvals`, req),
  };
}
