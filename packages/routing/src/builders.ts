export function loginPath(params?: { registered?: boolean }): string {
  if (params?.registered) return '/login?registered=1';
  return '/login';
}

export function workspacePath(workspaceId: string): string {
  return `/workspaces/${workspaceId}`;
}

export function tasksPath(workspaceId: string): string {
  return `/workspaces/${workspaceId}/tasks`;
}

export function taskDetailPath(workspaceId: string, taskId: string): string {
  return `/workspaces/${workspaceId}/tasks/${taskId}`;
}

export function taskNewPath(workspaceId: string): string {
  return `/workspaces/${workspaceId}/tasks/new`;
}

export function taskEditPath(workspaceId: string, taskId: string): string {
  return `/workspaces/${workspaceId}/tasks/${taskId}/edit`;
}

export function taskReviewPath(workspaceId: string, taskId: string): string {
  return `/workspaces/${workspaceId}/tasks/${taskId}/review`;
}

export function runDetailPath(workspaceId: string, runId: string): string {
  return `/workspaces/${workspaceId}/runs/${runId}`;
}

export function artifactsPath(workspaceId: string): string {
  return `/workspaces/${workspaceId}/artifacts`;
}

export function artifactDetailPath(workspaceId: string, artifactId: string): string {
  return `/workspaces/${workspaceId}/artifacts/${artifactId}`;
}

export function settingsPath(workspaceId: string): string {
  return `/workspaces/${workspaceId}/settings`;
}

export function membersPath(workspaceId: string): string {
  return `/workspaces/${workspaceId}/settings/members`;
}

export function policiesPath(workspaceId: string): string {
  return `/workspaces/${workspaceId}/settings/policies`;
}

export function secretsPath(workspaceId: string): string {
  return `/workspaces/${workspaceId}/settings/secrets`;
}

export function integrationsPath(workspaceId: string): string {
  return `/workspaces/${workspaceId}/settings/integrations`;
}

export function activityPath(workspaceId: string): string {
  return `/workspaces/${workspaceId}/activity`;
}

export function notificationsPath(workspaceId: string): string {
  return `/workspaces/${workspaceId}/notifications`;
}

export function approvalsPath(workspaceId: string): string {
  return `/workspaces/${workspaceId}/approvals`;
}

export function approvalDetailPath(workspaceId: string, approvalId: string): string {
  return `/workspaces/${workspaceId}/approvals/${approvalId}`;
}

export function reviewQueuePath(workspaceId: string): string {
  return `/workspaces/${workspaceId}/review`;
}

export function terminalPath(workspaceId: string, runId: string): string {
  return `/workspaces/${workspaceId}/runs/${runId}/terminal`;
}
