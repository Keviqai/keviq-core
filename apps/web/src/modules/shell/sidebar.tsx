'use client';

import Link from 'next/link';
import { useParams, usePathname } from 'next/navigation';
import { tasksPath, artifactsPath, approvalsPath, reviewQueuePath, workspacePath, activityPath, settingsPath } from '@keviq/routing';
import { useSidebarStore } from '@keviq/ui-state';
import { usePendingApprovalCount } from '@keviq/server-state';
import { LogoIcon } from '@/modules/brand/logo-brand';

interface NavItem {
  label: string;
  href: string;
  badge?: number | null;
  section?: 'main' | 'ops';
}

export function Sidebar() {
  const params = useParams<{ workspaceId: string }>();
  const pathname = usePathname();
  const { isOpen } = useSidebarStore();

  const workspaceId = params.workspaceId ?? '';
  const { data: pendingCount } = usePendingApprovalCount(workspaceId);
  const reviewCount = pendingCount?.pending_count ?? 0;

  const mainItems: NavItem[] = !workspaceId ? [] : [
    { label: 'Overview', href: workspacePath(workspaceId) },
    { label: 'Tasks', href: tasksPath(workspaceId) },
    { label: 'Approval History', href: approvalsPath(workspaceId) },
    { label: 'Needs Review', href: reviewQueuePath(workspaceId), badge: reviewCount > 0 ? reviewCount : null },
    { label: 'Outputs', href: artifactsPath(workspaceId) },
    { label: 'Activity', href: activityPath(workspaceId) },
  ];

  const opsItems: NavItem[] = [
    ...(workspaceId ? [{ label: 'Settings', href: settingsPath(workspaceId) }] : []),
    { label: 'System Health', href: '/health' },
  ];

  if (!isOpen) {
    return (
      <aside style={{ width: 48, borderRight: '1px solid #e5e7eb', padding: '12px 8px', display: 'flex', flexDirection: 'column', alignItems: 'center' }}>
        <button onClick={useSidebarStore.getState().toggle} aria-label="Open sidebar" style={{ cursor: 'pointer', background: 'none', border: 'none', padding: 4 }}>
          <LogoIcon size={24} />
        </button>
      </aside>
    );
  }

  return (
    <aside style={{ width: 220, borderRight: '1px solid #e5e7eb', padding: 16, display: 'flex', flexDirection: 'column' }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 24 }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
          <LogoIcon size={24} />
          <strong style={{ letterSpacing: '0.03em' }}>KEVIQ</strong>
        </div>
        <button onClick={useSidebarStore.getState().toggle} aria-label="Collapse sidebar" style={{ cursor: 'pointer' }}>
          &#x2190;
        </button>
      </div>
      <nav style={{ flex: 1 }}>
        <ul style={{ listStyle: 'none', padding: 0, margin: 0 }}>
          {mainItems.map((item) => (
            <SidebarLink key={item.href} item={item} pathname={pathname} workspaceId={workspaceId} />
          ))}
        </ul>
        <div style={{ borderTop: '1px solid #f3f4f6', margin: '12px 0', paddingTop: 8 }}>
          <span style={{ fontSize: 11, color: '#9ca3af', fontWeight: 600, textTransform: 'uppercase', letterSpacing: '0.05em', padding: '0 12px' }}>
            System
          </span>
          <ul style={{ listStyle: 'none', padding: 0, margin: '4px 0 0' }}>
            {opsItems.map((item) => (
              <SidebarLink key={item.href} item={item} pathname={pathname} workspaceId={workspaceId} />
            ))}
          </ul>
        </div>
      </nav>
    </aside>
  );
}

function SidebarLink({ item, pathname, workspaceId }: { item: NavItem; pathname: string; workspaceId: string }) {
  const isOverview = item.href === workspacePath(workspaceId);
  const isActive = isOverview
    ? pathname === item.href
    : pathname === item.href || pathname.startsWith(item.href + '/');

  return (
    <li style={{ marginBottom: 2 }}>
      <Link
        href={item.href}
        style={{
          display: 'flex', justifyContent: 'space-between', alignItems: 'center',
          padding: '7px 12px', borderRadius: 6, textDecoration: 'none',
          color: isActive ? '#1d4ed8' : '#374151',
          backgroundColor: isActive ? '#eff6ff' : 'transparent',
          fontWeight: isActive ? 600 : 400,
          fontSize: 14,
        }}
      >
        <span>{item.label}</span>
        {item.badge != null && item.badge > 0 && (
          <span style={{
            backgroundColor: '#ef4444', color: '#fff', fontSize: 11,
            fontWeight: 700, borderRadius: 8, padding: '1px 6px',
            minWidth: 18, textAlign: 'center', lineHeight: '16px',
          }}>
            {item.badge > 99 ? '99+' : item.badge}
          </span>
        )}
      </Link>
    </li>
  );
}
