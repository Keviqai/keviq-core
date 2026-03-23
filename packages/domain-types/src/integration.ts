export interface Integration {
  id: string;
  workspace_id: string;
  name: string;
  integration_type: string;
  provider_kind: string;
  endpoint_url: string;
  default_model: string;
  api_key_secret_ref: string;
  description: string;
  is_enabled: boolean;
  config: Record<string, unknown> | null;
  created_by_id: string;
  created_at: string;
  updated_at: string;
}
