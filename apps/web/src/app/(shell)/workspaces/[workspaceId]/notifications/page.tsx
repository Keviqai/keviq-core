'use client';

import { useState } from 'react';
import { useParams, useRouter } from 'next/navigation';
import { useNotifications, useUnreadNotificationCount, useMarkNotificationRead, useMarkAllNotificationsRead } from '@keviq/server-state';
import type { Notification } from '@keviq/domain-types';
import { errorBoxStyle, errorTitleStyle, errorBodyStyle } from '@/modules/shared/ui-styles';

function formatRelativeTime(iso: string): string {
  const diff = Date.now() - new Date(iso).getTime();
  const mins = Math.floor(diff / 60000);
  if (mins < 1) return 'just now';
  if (mins < 60) return `${mins}m ago`;
  const hrs = Math.floor(mins / 60);
  if (hrs < 24) return `${hrs}h ago`;
  const days = Math.floor(hrs / 24);
  return `${days}d ago`;
}

function categoryColor(category: string): string {
  const map: Record<string, string> = {
    task: '#2563eb', run: '#7c3aed', approval: '#d97706',
    artifact: '#059669', workspace: '#6366f1', system: '#6b7280',
  };
  return map[category] ?? '#6b7280';
}

export default function NotificationsPage() {
  const params = useParams<{ workspaceId: string }>();
  const workspaceId = params.workspaceId;
  const router = useRouter();

  const [filter, setFilter] = useState<'all' | 'unread'>('all');

  const isReadParam = filter === 'unread' ? false : undefined;
  const { data: notifications, isLoading, isError, error } = useNotifications(workspaceId, { is_read: isReadParam });
  const { data: countData } = useUnreadNotificationCount(workspaceId);
  const markReadMut = useMarkNotificationRead();
  const markAllMut = useMarkAllNotificationsRead();

  const unreadCount = countData?.unread_count ?? 0;
  const items = notifications ?? [];

  const handleClick = async (n: Notification) => {
    if (!n.is_read) {
      try {
        await markReadMut.mutateAsync({ workspaceId, notificationId: n.id });
      } catch {
        // silent — still navigate
      }
    }
    if (n.link && n.link.startsWith('/') && !n.link.startsWith('//')) {
      router.push(n.link);
    }
  };

  const handleMarkAll = () => {
    markAllMut.mutate({ workspaceId });
  };

  return (
    <div>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 16 }}>
        <h1 style={{ fontSize: 24, fontWeight: 700, margin: 0 }}>
          Notifications
          {unreadCount > 0 && (
            <span style={{
              marginLeft: 8, fontSize: 13, fontWeight: 600, color: '#fff',
              backgroundColor: '#ef4444', borderRadius: 10, padding: '2px 8px',
            }}>
              {unreadCount}
            </span>
          )}
        </h1>
        {unreadCount > 0 && (
          <button
            onClick={handleMarkAll}
            disabled={markAllMut.isPending}
            style={{
              padding: '6px 14px', fontSize: 13, borderRadius: 6, border: '1px solid #d1d5db',
              backgroundColor: '#fff', color: '#374151', cursor: 'pointer',
            }}
          >
            {markAllMut.isPending ? 'Marking...' : 'Mark all as read'}
          </button>
        )}
      </div>

      {/* Filter tabs */}
      <div style={{ display: 'flex', gap: 8, marginBottom: 16 }}>
        {(['all', 'unread'] as const).map((f) => (
          <button
            key={f}
            onClick={() => setFilter(f)}
            style={{
              padding: '6px 14px', fontSize: 13, borderRadius: 6, cursor: 'pointer',
              border: filter === f ? '1px solid #2563eb' : '1px solid #d1d5db',
              backgroundColor: filter === f ? '#eff6ff' : '#fff',
              color: filter === f ? '#1d4ed8' : '#374151',
              fontWeight: filter === f ? 600 : 400,
            }}
          >
            {f === 'all' ? 'All' : 'Unread'}
          </button>
        ))}
      </div>

      {isLoading ? (
        <p style={{ color: '#6b7280' }}>Loading notifications...</p>
      ) : isError ? (
        <div style={errorBoxStyle} role="alert">
          <p style={errorTitleStyle}>Failed to load notifications</p>
          <p style={errorBodyStyle}>{error instanceof Error ? error.message : 'An unexpected error occurred.'}</p>
        </div>
      ) : items.length === 0 ? (
        <div style={{ padding: 32, textAlign: 'center', border: '1px dashed #d1d5db', borderRadius: 8 }}>
          <p style={{ fontSize: 14, color: '#374151', marginBottom: 4 }}>No notifications</p>
          <p style={{ fontSize: 13, color: '#6b7280', margin: 0 }}>You're all caught up.</p>
        </div>
      ) : (
        <div style={{ border: '1px solid #e5e7eb', borderRadius: 8, overflow: 'hidden' }}>
          {items.map((n) => (
            <div
              key={n.id}
              onClick={() => handleClick(n)}
              style={{
                padding: '12px 14px', borderBottom: '1px solid #f3f4f6',
                display: 'flex', alignItems: 'flex-start', gap: 10,
                cursor: n.link ? 'pointer' : 'default',
                backgroundColor: n.is_read ? '#fff' : '#f0f9ff',
              }}
            >
              {/* Unread dot */}
              <span style={{
                width: 8, height: 8, borderRadius: '50%', marginTop: 5, flexShrink: 0,
                backgroundColor: n.is_read ? 'transparent' : '#2563eb',
              }} />
              <div style={{ flex: 1, minWidth: 0 }}>
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 2 }}>
                  <span style={{ fontSize: 14, fontWeight: n.is_read ? 400 : 600, color: '#1f2937' }}>
                    {n.title}
                  </span>
                  <span style={{ fontSize: 12, color: '#9ca3af', whiteSpace: 'nowrap', marginLeft: 8 }}>
                    {formatRelativeTime(n.created_at)}
                  </span>
                </div>
                {n.body && (
                  <p style={{ fontSize: 13, color: '#6b7280', margin: 0, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                    {n.body}
                  </p>
                )}
                <span style={{
                  fontSize: 11, marginTop: 4, display: 'inline-block',
                  padding: '1px 6px', borderRadius: 4,
                  backgroundColor: '#f3f4f6', color: categoryColor(n.category),
                }}>
                  {n.category}
                </span>
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
