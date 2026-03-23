export interface Secret {
  id: string;
  workspace_id: string;
  name: string;
  description: string;
  secret_type: string;
  masked_display: string;
  created_by_id: string;
  created_at: string;
  updated_at: string;
}
