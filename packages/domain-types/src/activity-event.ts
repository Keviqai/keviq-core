export interface ActivityEvent {
  event_id: string;
  event_type: string;
  workspace_id: string;
  task_id?: string;
  run_id?: string;
  step_id?: string;
  correlation_id: string;
  occurred_at: string;
  emitted_by: Record<string, string>;
  actor: Record<string, string>;
  payload: Record<string, unknown>;
}

export interface ActivityResponse {
  workspace_id: string;
  events: ActivityEvent[];
  count: number;
  total_count: number;
}
