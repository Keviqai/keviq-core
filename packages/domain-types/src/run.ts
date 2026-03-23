import type { Capabilities } from './capabilities';

export type RunStatus =
  | 'pending'
  | 'running'
  | 'completed'
  | 'failed'
  | 'timed_out'
  | 'cancelled';

export interface Run {
  run_id: string;
  task_id: string;
  workspace_id: string;
  run_status: RunStatus;
  attempt_number: number;
  started_at: string | null;
  completed_at: string | null;
  error_summary: string | null;
  sandbox_id?: string | null;
  _capabilities?: Capabilities;
}
