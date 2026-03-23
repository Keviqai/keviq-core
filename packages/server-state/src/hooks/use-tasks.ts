'use client';

import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { createTasksApi } from '@keviq/api-client';
import type { CancelTaskResponse, CreateTaskRequest, CreateTaskResponse, CreateDraftRequest, RetryTaskResponse } from '@keviq/api-client';
import type { Task } from '@keviq/domain-types';
import { apiClient } from '../api';
import { queryKeys } from '../query-keys';

const tasksApi = createTasksApi(apiClient);

export function useTaskList(workspaceId: string) {
  return useQuery({
    queryKey: queryKeys.tasks.list(workspaceId),
    queryFn: () => tasksApi.list(workspaceId),
    enabled: !!workspaceId,
  });
}

export function useTask(taskId: string) {
  return useQuery({
    queryKey: queryKeys.tasks.detail(taskId),
    queryFn: () => tasksApi.get(taskId),
    enabled: !!taskId,
  });
}

export function useCreateTask() {
  const qc = useQueryClient();
  return useMutation<CreateTaskResponse, Error, CreateTaskRequest>({
    mutationFn: (req) => tasksApi.create(req),
    onSuccess: (_data, variables) => {
      qc.invalidateQueries({ queryKey: queryKeys.tasks.list(variables.workspace_id) });
    },
  });
}

export function useCreateTaskDraft() {
  const qc = useQueryClient();
  return useMutation<Task, Error, CreateDraftRequest>({
    mutationFn: (req) => tasksApi.createDraft(req),
    onSuccess: (_data, variables) => {
      qc.invalidateQueries({ queryKey: queryKeys.tasks.list(variables.workspace_id) });
    },
  });
}

export function useUpdateTaskBrief(workspaceId: string) {
  const qc = useQueryClient();
  return useMutation<Task, Error, { taskId: string; updates: Record<string, unknown> }>({
    mutationFn: ({ taskId, updates }) => tasksApi.updateBrief(taskId, updates),
    onSuccess: (data) => {
      qc.invalidateQueries({ queryKey: queryKeys.tasks.detail(data.task_id) });
      qc.invalidateQueries({ queryKey: queryKeys.tasks.list(workspaceId) });
    },
  });
}

export function useLaunchTask(workspaceId: string) {
  const qc = useQueryClient();
  return useMutation<CreateTaskResponse, Error, string>({
    mutationFn: (taskId) => tasksApi.launch(taskId),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: queryKeys.tasks.list(workspaceId) });
    },
  });
}

export function useCancelTask(workspaceId: string) {
  const qc = useQueryClient();
  return useMutation<CancelTaskResponse, Error, string>({
    mutationFn: (taskId) => tasksApi.cancel(taskId),
    onSuccess: (_data, taskId) => {
      qc.invalidateQueries({ queryKey: queryKeys.tasks.detail(taskId) });
      qc.invalidateQueries({ queryKey: queryKeys.tasks.list(workspaceId) });
    },
  });
}

export function useRetryTask(workspaceId: string) {
  const qc = useQueryClient();
  return useMutation<RetryTaskResponse, Error, string>({
    mutationFn: (taskId) => tasksApi.retry(taskId),
    onSuccess: (_data, taskId) => {
      qc.invalidateQueries({ queryKey: queryKeys.tasks.detail(taskId) });
      qc.invalidateQueries({ queryKey: queryKeys.tasks.list(workspaceId) });
    },
  });
}
