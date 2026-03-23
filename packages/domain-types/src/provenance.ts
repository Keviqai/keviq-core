export interface ArtifactProvenance {
  id: string;
  artifact_id: string;
  model_provider: string | null;
  model_name_concrete: string | null;
  model_version_concrete: string | null;
  model_temperature: number | null;
  model_max_tokens: number | null;
  system_prompt_hash: string | null;
  run_config_hash: string | null;
  tool_name: string | null;
  tool_version: string | null;
  tool_config_hash: string | null;
  input_snapshot: Record<string, unknown> | null;
  created_at: string;
}
