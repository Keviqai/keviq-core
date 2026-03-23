'use client';

import { useRouter, useParams } from 'next/navigation';
import { useQueryClient } from '@tanstack/react-query';
import { useAuth, useUnreadNotificationCount } from '@keviq/server-state';
import { notificationsPath } from '@keviq/routing';
import { clearAuthCookie } from '@/modules/auth/cookie';
import { WorkspaceSelector } from './workspace-selector';

export function TopBar() {
  const { data } = useAuth();
  const router = useRouter();
  const queryClient = useQueryClient();
  const params = useParams<{ workspaceId: string }>();
  const workspaceId = params.workspaceId;

  const { data: countData } = useUnreadNotificationCount(workspaceId ?? '');
  const unreadCount = countData?.unread_count ?? 0;

  function handleLogout() {
    clearAuthCookie();
    queryClient.clear();
    router.push('/login');
  }

  return (
    <header
      style={{
        height: 48,
        borderBottom: '1px solid #e5e7eb',
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'space-between',
        padding: '0 16px',
      }}
    >
      <WorkspaceSelector />
      <div style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
        {data && (
          <span style={{ fontSize: 13, color: '#6b7280' }} title={(data as any).email ?? data.user?.email ?? ''}>
            {(data as any).display_name ?? data.user?.display_name ?? (data as any).email ?? data.user?.email ?? ''}
          </span>
        )}
        {workspaceId && (
          <button
            onClick={() => router.push(notificationsPath(workspaceId))}
            style={{
              background: 'none',
              border: 'none',
              cursor: 'pointer',
              position: 'relative',
              padding: '4px',
              fontSize: 18,
              color: '#6b7280',
            }}
            title="Notifications"
            aria-label="Notifications"
          >
            &#128276;
            {unreadCount > 0 && (
              <span
                role="status"
                aria-live="polite"
                aria-label={`${unreadCount} unread notifications`}
                style={{
                  position: 'absolute', top: 0, right: -4,
                  backgroundColor: '#ef4444', color: '#fff',
                  fontSize: 10, fontWeight: 700, borderRadius: 8,
                  padding: '1px 5px', lineHeight: '14px',
                  minWidth: 16, textAlign: 'center',
                }}
              >
                {unreadCount > 99 ? '99+' : unreadCount}
              </span>
            )}
          </button>
        )}
        <button
          onClick={handleLogout}
          style={{
            background: 'none',
            border: '1px solid #d1d5db',
            borderRadius: 4,
            padding: '4px 10px',
            fontSize: 13,
            color: '#6b7280',
            cursor: 'pointer',
          }}
          aria-label="Sign out"
        >
          Sign out
        </button>
      </div>
    </header>
  );
}
