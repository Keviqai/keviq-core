import type { ApiClient } from './client';
import type { TimelineEvent } from '@keviq/domain-types';

export interface TimelineResponse {
  events: TimelineEvent[];
  count: number;
}

export interface TimelineApi {
  taskTimeline: (taskId: string, workspaceId: string, after?: string) => Promise<TimelineResponse>;
  runTimeline: (runId: string, workspaceId: string, after?: string) => Promise<TimelineResponse>;
}

export function createTimelineApi(client: ApiClient): TimelineApi {
  return {
    taskTimeline: (taskId, workspaceId, after) => {
      const qs = new URLSearchParams({ workspace_id: workspaceId });
      if (after) qs.set('after', after);
      return client.get(`/v1/tasks/${encodeURIComponent(taskId)}/timeline?${qs}`);
    },
    runTimeline: (runId, workspaceId, after) => {
      const qs = new URLSearchParams({ workspace_id: workspaceId });
      if (after) qs.set('after', after);
      return client.get(`/v1/runs/${encodeURIComponent(runId)}/timeline?${qs}`);
    },
  };
}
