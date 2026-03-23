export interface Policy {
  id: string;
  workspace_id: string;
  name: string;
  scope: string;
  rules: unknown[];
  is_default: boolean;
  created_at: string;
  updated_at: string;
}
