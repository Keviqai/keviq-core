import type { Capabilities } from './capabilities';

export type TaskStatus =
  | 'draft'
  | 'pending'
  | 'running'
  | 'waiting_approval'
  | 'completed'
  | 'failed'
  | 'cancelled'
  | 'archived';

export interface Task {
  task_id: string;
  workspace_id: string;
  title: string;
  description: string | null;
  task_type: string;
  task_status: TaskStatus;
  created_by_id: string;
  latest_run_id: string | null;
  created_at: string;
  updated_at: string;
  // Q1 brief fields
  goal: string | null;
  context: string | null;
  constraints: string | null;
  desired_output: string | null;
  risk_level: string | null;
  template_id?: string;
  agent_template_id?: string;
  _capabilities?: Capabilities;
}
