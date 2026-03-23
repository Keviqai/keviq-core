/** Task comment — inline discussion on a task. */
export interface TaskComment {
  id: string;
  workspace_id: string;
  task_id: string;
  author_id: string;
  body: string;
  created_at: string;
}
