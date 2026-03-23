export interface TaskCapabilities {
  can_cancel: boolean;
  can_view_run: boolean;
}

export interface WorkspaceCapabilities {
  can_manage_members: boolean;
  can_manage_policies: boolean;
  can_create_task: boolean;
}
