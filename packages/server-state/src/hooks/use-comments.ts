'use client';

import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { createCommentsApi } from '@keviq/api-client';
import { apiClient } from '../api';
import { queryKeys } from '../query-keys';

const commentsApi = createCommentsApi(apiClient);

export function useTaskComments(workspaceId: string, taskId: string) {
  return useQuery({
    queryKey: queryKeys.comments.task(workspaceId, taskId),
    queryFn: () => commentsApi.listTaskComments(workspaceId, taskId),
    enabled: !!workspaceId && !!taskId,
    staleTime: 10_000,
  });
}

export function useCreateTaskComment(workspaceId: string, taskId: string) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (body: string) => commentsApi.createTaskComment(workspaceId, taskId, body),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: queryKeys.comments.task(workspaceId, taskId) });
    },
  });
}
