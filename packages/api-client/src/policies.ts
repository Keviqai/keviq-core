import type { ApiClient } from './client';
import type { Policy } from '@keviq/domain-types';

export interface CreatePolicyRequest {
  name: string;
  scope?: string;
  rules?: unknown[];
}

export interface UpdatePolicyRequest {
  name?: string;
  scope?: string;
  rules?: unknown[];
}

export interface PoliciesApi {
  list: (workspaceId: string) => Promise<Policy[]>;
  get: (workspaceId: string, policyId: string) => Promise<Policy>;
  create: (workspaceId: string, req: CreatePolicyRequest) => Promise<Policy>;
  update: (workspaceId: string, policyId: string, req: UpdatePolicyRequest) => Promise<Policy>;
}

export function createPoliciesApi(client: ApiClient): PoliciesApi {
  return {
    list: (workspaceId) =>
      client.get(`/v1/workspaces/${encodeURIComponent(workspaceId)}/policies`),
    get: (workspaceId, policyId) =>
      client.get(`/v1/workspaces/${encodeURIComponent(workspaceId)}/policies/${encodeURIComponent(policyId)}`),
    create: (workspaceId, req) =>
      client.post(`/v1/workspaces/${encodeURIComponent(workspaceId)}/policies`, req),
    update: (workspaceId, policyId, req) =>
      client.patch(`/v1/workspaces/${encodeURIComponent(workspaceId)}/policies/${encodeURIComponent(policyId)}`, req),
  };
}
