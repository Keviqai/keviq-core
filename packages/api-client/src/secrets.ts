import type { ApiClient } from './client';
import type { Secret } from '@keviq/domain-types';

export interface CreateSecretRequest {
  name: string;
  description?: string;
  secret_type: string;
  value: string;
}

export interface UpdateSecretMetadataRequest {
  name?: string;
  description?: string;
}

export interface SecretsApi {
  list: (workspaceId: string) => Promise<Secret[]>;
  create: (workspaceId: string, req: CreateSecretRequest) => Promise<Secret>;
  remove: (workspaceId: string, secretId: string) => Promise<void>;
  updateMetadata: (workspaceId: string, secretId: string, req: UpdateSecretMetadataRequest) => Promise<Secret>;
}

export function createSecretsApi(client: ApiClient): SecretsApi {
  return {
    list: (workspaceId) =>
      client.get(`/v1/workspaces/${encodeURIComponent(workspaceId)}/secrets`),
    create: (workspaceId, req) =>
      client.post(`/v1/workspaces/${encodeURIComponent(workspaceId)}/secrets`, req),
    remove: (workspaceId, secretId) =>
      client.delete(`/v1/workspaces/${encodeURIComponent(workspaceId)}/secrets/${encodeURIComponent(secretId)}`),
    updateMetadata: (workspaceId, secretId, req) =>
      client.patch(
        `/v1/workspaces/${encodeURIComponent(workspaceId)}/secrets/${encodeURIComponent(secretId)}`,
        req,
      ),
  };
}
