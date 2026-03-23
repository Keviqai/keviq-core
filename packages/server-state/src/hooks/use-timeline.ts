'use client';

import { useQuery } from '@tanstack/react-query';
import { createTimelineApi } from '@keviq/api-client';
import { apiClient } from '../api';
import { queryKeys } from '../query-keys';

const timelineApi = createTimelineApi(apiClient);

export function useTaskTimeline(taskId: string, workspaceId: string) {
  return useQuery({
    queryKey: queryKeys.timeline.task(taskId),
    queryFn: () => timelineApi.taskTimeline(taskId, workspaceId),
    enabled: !!taskId && !!workspaceId,
    staleTime: 30_000,
  });
}

export function useRunTimeline(runId: string, workspaceId: string) {
  return useQuery({
    queryKey: queryKeys.timeline.run(runId),
    queryFn: () => timelineApi.runTimeline(runId, workspaceId),
    enabled: !!runId && !!workspaceId,
    staleTime: 30_000,
  });
}
