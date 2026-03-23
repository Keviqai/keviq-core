export interface TimelineEvent {
  event_id: string;
  event_type: string;
  schema_version: string;
  workspace_id: string;
  task_id: string | null;
  run_id: string | null;
  step_id: string | null;
  artifact_id: string | null;
  correlation_id: string;
  causation_id: string | null;
  occurred_at: string;
  emitted_by: {
    service: string;
    instance_id: string;
  };
  actor: {
    type: 'user' | 'agent' | 'system' | 'scheduler';
    id: string;
  };
  payload: Record<string, unknown>;
}
