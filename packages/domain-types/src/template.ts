export interface TaskTemplate {
  template_id: string;
  name: string;
  description: string | null;
  category: string;
  prefilled_fields: Record<string, string>;
  expected_output_type: string | null;
  scope: string;
  created_at: string;
  updated_at: string;
}

export interface AgentTemplate {
  template_id: string;
  name: string;
  description: string | null;
  best_for: string | null;
  not_for: string | null;
  capabilities_manifest: string[];
  default_output_types: string[];
  default_risk_profile: string;
  scope: string;
  created_at: string;
  updated_at: string;
}
