export type ApprovalDecision = 'pending' | 'approved' | 'rejected' | 'timed_out' | 'cancelled';
export type ApprovalTargetType = 'task' | 'run' | 'step' | 'artifact' | 'tool_call';

export interface ArtifactContextSummary {
  name: string | null;
  artifact_type: string | null;
  artifact_status: string | null;
  size_bytes: number | null;
  annotation_count: number | null;
}

export interface ApprovalRequest {
  approval_id: string;
  workspace_id: string;
  target_type: ApprovalTargetType;
  target_id: string;
  requested_by: string;
  reviewer_id: string | null;
  prompt: string | null;
  timeout_at: string | null;
  decision: ApprovalDecision;
  decided_by_id: string | null;
  decided_at: string | null;
  decision_comment: string | null;
  created_at: string;
  updated_at: string;
  /** Only present when target_type === 'artifact' and artifact-service is reachable */
  artifact_context?: ArtifactContextSummary | null;
  /** Artifact display name — present in list and detail when target_type === 'artifact' */
  artifact_name?: string | null;
  /** Tool context — present when target_type === 'tool_call' (O5-S1) */
  tool_context?: ToolApprovalContext | null;
}

/** Context for tool_call approval requests — what tool needs human approval and why */
export interface ToolApprovalContext {
  invocation_id: string;
  run_id: string;
  task_id: string;
  tool_name: string;
  risk_reason: string;
  arguments_preview: string;
}
