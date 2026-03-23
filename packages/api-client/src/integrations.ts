import type { ApiClient } from './client';
import type { Integration } from '@keviq/domain-types';

export interface CreateIntegrationRequest {
  name: string;
  integration_type: string;
  provider_kind: string;
  endpoint_url?: string;
  default_model?: string;
  api_key_secret_ref?: string;
  description?: string;
  is_enabled?: boolean;
}

export interface UpdateIntegrationRequest {
  name?: string;
  provider_kind?: string;
  endpoint_url?: string;
  default_model?: string;
  api_key_secret_ref?: string;
  description?: string;
  is_enabled?: boolean;
}

export interface IntegrationsApi {
  list: (workspaceId: string) => Promise<Integration[]>;
  get: (workspaceId: string, integrationId: string) => Promise<Integration>;
  create: (workspaceId: string, req: CreateIntegrationRequest) => Promise<Integration>;
  update: (workspaceId: string, integrationId: string, req: UpdateIntegrationRequest) => Promise<Integration>;
  remove: (workspaceId: string, integrationId: string) => Promise<void>;
  toggle: (workspaceId: string, integrationId: string) => Promise<Integration>;
}

export function createIntegrationsApi(client: ApiClient): IntegrationsApi {
  return {
    list: (workspaceId) =>
      client.get(`/v1/workspaces/${encodeURIComponent(workspaceId)}/integrations`),
    get: (workspaceId, integrationId) =>
      client.get(`/v1/workspaces/${encodeURIComponent(workspaceId)}/integrations/${encodeURIComponent(integrationId)}`),
    create: (workspaceId, req) =>
      client.post(`/v1/workspaces/${encodeURIComponent(workspaceId)}/integrations`, req),
    update: (workspaceId, integrationId, req) =>
      client.patch(
        `/v1/workspaces/${encodeURIComponent(workspaceId)}/integrations/${encodeURIComponent(integrationId)}`,
        req,
      ),
    remove: (workspaceId, integrationId) =>
      client.delete(`/v1/workspaces/${encodeURIComponent(workspaceId)}/integrations/${encodeURIComponent(integrationId)}`),
    toggle: (workspaceId, integrationId) =>
      client.post(
        `/v1/workspaces/${encodeURIComponent(workspaceId)}/integrations/${encodeURIComponent(integrationId)}/toggle`,
        {},
      ),
  };
}
