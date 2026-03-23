import type { Capabilities } from './capabilities';

export type ArtifactStatus = 'pending' | 'writing' | 'ready' | 'failed';

export interface ArtifactAnnotation {
  id: string;
  artifact_id: string;
  workspace_id: string;
  author_id: string;
  body: string;
  created_at: string;
}

export type ArtifactType =
  | 'code_file'
  | 'document'
  | 'data_output'
  | 'log'
  | 'config'
  | 'report'
  | 'model_output';

export interface Artifact {
  id: string;
  workspace_id: string;
  task_id: string;
  run_id: string;
  step_id: string | null;
  agent_invocation_id: string | null;
  artifact_type: string;
  artifact_status: ArtifactStatus;
  root_type: string;
  name: string;
  mime_type: string | null;
  size_bytes: number | null;
  checksum: string | null;
  lineage: Record<string, unknown> | null;
  metadata: Record<string, unknown> | null;
  created_at: string;
  updated_at: string;
  ready_at: string | null;
  failed_at: string | null;
  _capabilities?: Capabilities;
}
