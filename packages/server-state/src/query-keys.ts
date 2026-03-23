export const queryKeys = {
  auth: {
    me: ['auth', 'me'] as const,
  },
  workspaces: {
    list: ['workspaces'] as const,
    detail: (id: string) => ['workspaces', id] as const,
  },
  tasks: {
    list: (workspaceId: string) => ['tasks', { workspaceId }] as const,
    detail: (taskId: string) => ['tasks', taskId] as const,
  },
  runs: {
    listByTask: (taskId: string) => ['runs', { taskId }] as const,
    detail: (runId: string) => ['runs', runId] as const,
  },
  steps: {
    listByRun: (runId: string) => ['steps', { runId }] as const,
  },
  timeline: {
    task: (taskId: string) => ['timeline', 'task', taskId] as const,
    run: (runId: string) => ['timeline', 'run', runId] as const,
  },
  members: {
    list: (workspaceId: string) => ['members', { workspaceId }] as const,
  },
  terminal: {
    session: (sessionId: string) => ['terminal', sessionId] as const,
    history: (sessionId: string) => ['terminal', sessionId, 'history'] as const,
  },
  approvals: {
    list: (workspaceId: string, decision?: string, reviewerId?: string) =>
      ['approvals', { workspaceId, decision, reviewerId }] as const,
    detail: (workspaceId: string, approvalId: string) =>
      ['approvals', approvalId, { workspaceId }] as const,
    count: (workspaceId: string) =>
      ['approvals', 'count', { workspaceId }] as const,
  },
  policies: {
    list: (workspaceId: string) => ['policies', { workspaceId }] as const,
  },
  secrets: {
    list: (workspaceId: string) => ['secrets', { workspaceId }] as const,
  },
  activity: {
    list: (workspaceId: string, params?: Record<string, unknown>) =>
      ['activity', { workspaceId, ...params }] as const,
  },
  notifications: {
    list: (workspaceId: string, params?: Record<string, unknown>) =>
      ['notifications', { workspaceId, ...params }] as const,
    count: (workspaceId: string) =>
      ['notifications', 'count', { workspaceId }] as const,
  },
  integrations: {
    list: (workspaceId: string) => ['integrations', { workspaceId }] as const,
    detail: (workspaceId: string, integrationId: string) =>
      ['integrations', integrationId, { workspaceId }] as const,
  },
  taskTemplates: {
    list: (category?: string) => ['taskTemplates', { category }] as const,
    detail: (id: string) => ['taskTemplates', id] as const,
  },
  agentTemplates: {
    list: ['agentTemplates'] as const,
    detail: (id: string) => ['agentTemplates', id] as const,
  },
  comments: {
    task: (workspaceId: string, taskId: string) => ['comments', 'task', { workspaceId, taskId }] as const,
  },
  telemetry: {
    metrics: (service?: string) => ['telemetry', 'metrics', { service }] as const,
  },
  executions: {
    detail: (executionId: string) => ['executions', executionId] as const,
  },
  sandboxes: {
    detail: (sandboxId: string) => ['sandboxes', sandboxId] as const,
  },
  artifacts: {
    list: (workspaceId: string) => ['artifacts', { workspaceId }] as const,
    listByRun: (workspaceId: string, runId: string) =>
      ['artifacts', { workspaceId, runId }] as const,
    detail: (workspaceId: string, artifactId: string) =>
      ['artifacts', artifactId, { workspaceId }] as const,
    provenance: (workspaceId: string, artifactId: string) =>
      ['artifacts', artifactId, 'provenance', { workspaceId }] as const,
    lineage: (workspaceId: string, artifactId: string) =>
      ['artifacts', artifactId, 'lineage', { workspaceId }] as const,
    preview: (workspaceId: string, artifactId: string) =>
      ['artifacts', artifactId, 'preview', { workspaceId }] as const,
    annotations: (workspaceId: string, artifactId: string) =>
      ['artifacts', artifactId, 'annotations', { workspaceId }] as const,
  },
};
