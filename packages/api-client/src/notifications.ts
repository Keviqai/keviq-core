import type { ApiClient } from './client';
import type { Notification } from '@keviq/domain-types';

export interface NotificationQueryParams {
  is_read?: boolean;
  limit?: number;
  offset?: number;
}

export interface UnreadCountResponse {
  workspace_id: string;
  unread_count: number;
}

export interface NotificationsApi {
  list: (workspaceId: string, params?: NotificationQueryParams) => Promise<Notification[]>;
  countUnread: (workspaceId: string) => Promise<UnreadCountResponse>;
  markRead: (workspaceId: string, notificationId: string) => Promise<void>;
  markAllRead: (workspaceId: string) => Promise<{ marked_count: number }>;
}

export function createNotificationsApi(client: ApiClient): NotificationsApi {
  return {
    list: (workspaceId, params) => {
      const qs = new URLSearchParams();
      if (params?.is_read !== undefined) qs.set('is_read', String(params.is_read));
      if (params?.limit !== undefined) qs.set('limit', String(params.limit));
      if (params?.offset !== undefined) qs.set('offset', String(params.offset));
      const suffix = qs.toString() ? `?${qs.toString()}` : '';
      return client.get(`/v1/workspaces/${encodeURIComponent(workspaceId)}/notifications${suffix}`);
    },
    countUnread: (workspaceId) =>
      client.get(`/v1/workspaces/${encodeURIComponent(workspaceId)}/notifications/count`),
    markRead: (workspaceId, notificationId) =>
      client.post(
        `/v1/workspaces/${encodeURIComponent(workspaceId)}/notifications/${encodeURIComponent(notificationId)}/read`,
        {},
      ),
    markAllRead: (workspaceId) =>
      client.post(`/v1/workspaces/${encodeURIComponent(workspaceId)}/notifications/read-all`, {}),
  };
}
