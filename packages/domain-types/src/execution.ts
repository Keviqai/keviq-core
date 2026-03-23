/** Tool execution detail — full attempt record from execution-service. */
export interface ToolExecutionDetail {
  execution_id: string;
  sandbox_id: string;
  attempt_index: number;
  tool_name: string;
  tool_input: Record<string, unknown> | null;
  status: 'pending' | 'running' | 'completed' | 'failed' | 'timed_out';
  stdout: string | null;
  stderr: string | null;
  exit_code: number | null;
  truncated: boolean;
  error_detail: Record<string, unknown> | null;
  started_at: string | null;
  completed_at: string | null;
}

/** Sandbox detail — sandbox metadata from execution-service. */
export interface SandboxDetail {
  sandbox_id: string;
  workspace_id: string;
  task_id: string;
  run_id: string;
  step_id: string;
  agent_invocation_id: string;
  sandbox_type: string;
  sandbox_status: string;
  started_at: string | null;
  terminated_at: string | null;
  termination_reason: string | null;
  created_at: string;
  updated_at: string;
}
