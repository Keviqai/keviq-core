'use client';

import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { createNotificationsApi } from '@keviq/api-client';
import type { NotificationQueryParams } from '@keviq/api-client';
import { apiClient } from '../api';
import { queryKeys } from '../query-keys';

const notificationsApi = createNotificationsApi(apiClient);

export function useNotifications(workspaceId: string, params?: NotificationQueryParams) {
  return useQuery({
    queryKey: queryKeys.notifications.list(workspaceId, params as Record<string, unknown> | undefined),
    queryFn: () => notificationsApi.list(workspaceId, params),
    enabled: !!workspaceId,
    staleTime: 15_000,
  });
}

export function useUnreadNotificationCount(workspaceId: string) {
  return useQuery({
    queryKey: queryKeys.notifications.count(workspaceId),
    queryFn: () => notificationsApi.countUnread(workspaceId),
    enabled: !!workspaceId,
    staleTime: 30_000,
  });
}

export function useMarkNotificationRead() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (vars: { workspaceId: string; notificationId: string }) =>
      notificationsApi.markRead(vars.workspaceId, vars.notificationId),
    onSuccess: (_data, variables) => {
      qc.invalidateQueries({ queryKey: ['notifications'] });
    },
  });
}

export function useMarkAllNotificationsRead() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (vars: { workspaceId: string }) =>
      notificationsApi.markAllRead(vars.workspaceId),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['notifications'] });
    },
  });
}
