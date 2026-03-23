export interface TerminalSession {
  id: string;
  sandbox_id: string;
  run_id: string;
  workspace_id: string;
  user_id: string;
  status: 'active' | 'closed';
  created_at: string;
  updated_at: string;
  closed_at: string | null;
}

export interface CommandResult {
  id: string;
  session_id: string;
  command: string;
  stdout: string;
  stderr: string;
  exit_code: number | null;
  status: 'running' | 'completed' | 'failed' | 'timed_out';
  created_at: string;
  completed_at: string | null;
}
