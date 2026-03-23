export type StepStatus =
  | 'pending'
  | 'running'
  | 'completed'
  | 'failed';

export interface Step {
  step_id: string;
  run_id: string;
  step_type: string;
  step_status: StepStatus;
  sequence_number: number;
  output_snapshot: Record<string, unknown> | null;
  error_detail: Record<string, unknown> | null;
  started_at: string | null;
  completed_at: string | null;
}
