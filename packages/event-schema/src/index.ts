// Event type constants — bổ sung dần theo doc 06
export const EventTypes = {
  TASK_SUBMITTED: 'task.submitted',
  TASK_COMPLETED: 'task.completed',
  TASK_FAILED: 'task.failed',
  TASK_CANCELLED: 'task.cancelled',
  RUN_STARTED: 'run.started',
  RUN_COMPLETED: 'run.completed',
  RUN_FAILED: 'run.failed',
  ARTIFACT_READY: 'artifact.ready',
  ARTIFACT_TAINTED: 'artifact.tainted',
} as const;

// Event envelope type
export interface EventEnvelope {
  event_id: string;
  event_type: string;
  schema_version: string;
  workspace_id: string;
  task_id?: string;
  run_id?: string;
  step_id?: string;
  agent_invocation_id?: string;
  sandbox_id?: string;
  artifact_id?: string;
  correlation_id: string;
  causation_id?: string;
  occurred_at: string;
  emitted_by: string;
  actor?: string;
  payload: Record<string, unknown>;
}
