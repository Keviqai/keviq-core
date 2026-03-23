'use client';

import { useState } from 'react';
import Link from 'next/link';
import { useParams } from 'next/navigation';
import { useTaskList, useWorkspaces } from '@keviq/server-state';
import { taskDetailPath, runDetailPath, taskNewPath } from '@keviq/routing';
import { StatusBadge } from '@/modules/shared/status-badge';

const STATUS_FILTERS = [
  { label: 'All', value: '' },
  { label: 'Draft', value: 'draft' },
  { label: 'Active', value: 'active' },
  { label: 'Completed', value: 'completed' },
  { label: 'Failed', value: 'failed' },
];

const ACTIVE_STATUSES = new Set(['pending', 'running', 'waiting_approval']);

function formatRelativeTime(iso: string): string {
  const diff = Date.now() - new Date(iso).getTime();
  const mins = Math.floor(diff / 60000);
  if (mins < 1) return 'just now';
  if (mins < 60) return `${mins}m ago`;
  const hrs = Math.floor(mins / 60);
  if (hrs < 24) return `${hrs}h ago`;
  const days = Math.floor(hrs / 24);
  if (days < 30) return `${days}d ago`;
  return new Date(iso).toLocaleDateString();
}

export default function TaskListPage() {
  const params = useParams<{ workspaceId: string }>();
  const workspaceId = params.workspaceId;
  const { data, isLoading, isError, error } = useTaskList(workspaceId);
  const { data: workspaces } = useWorkspaces();
  const [statusFilter, setStatusFilter] = useState('');

  const workspace = workspaces?.find((ws) => ws.id === workspaceId);
  const canCreateTask = workspace?._capabilities?.includes('task:create') ?? false;

  const allTasks = data?.items ?? [];
  const filteredTasks = statusFilter
    ? allTasks.filter((t) => {
        if (statusFilter === 'active') return ACTIVE_STATUSES.has(t.task_status);
        return t.task_status === statusFilter;
      })
    : allTasks;

  const statusCounts: Record<string, number> = {
    '': allTasks.length,
    draft: allTasks.filter((t) => t.task_status === 'draft').length,
    active: allTasks.filter((t) => ACTIVE_STATUSES.has(t.task_status)).length,
    completed: allTasks.filter((t) => t.task_status === 'completed').length,
    failed: allTasks.filter((t) => t.task_status === 'failed').length,
  };

  return (
    <div>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 16 }}>
        <h1 style={{ fontSize: 24, fontWeight: 700 }}>Tasks</h1>
        {canCreateTask && (
          <Link
            href={taskNewPath(workspaceId)}
            style={{
              display: 'inline-block',
              padding: '8px 16px',
              backgroundColor: '#1d4ed8',
              color: 'white',
              borderRadius: 6,
              fontSize: 14,
              fontWeight: 600,
              textDecoration: 'none',
            }}
          >
            + New Task
          </Link>
        )}
      </div>

      {/* Status filter tabs */}
      {!isLoading && allTasks.length > 0 && (
        <div style={{ display: 'flex', gap: 4, marginBottom: 16, flexWrap: 'wrap' }}>
          {STATUS_FILTERS.map((f) => (
            <button
              key={f.value}
              onClick={() => setStatusFilter(f.value)}
              style={{
                padding: '5px 12px',
                fontSize: 13,
                border: '1px solid',
                borderColor: statusFilter === f.value ? '#1d4ed8' : '#d1d5db',
                borderRadius: 6,
                backgroundColor: statusFilter === f.value ? '#eff6ff' : '#fff',
                color: statusFilter === f.value ? '#1d4ed8' : '#374151',
                cursor: 'pointer',
                fontWeight: statusFilter === f.value ? 600 : 400,
              }}
            >
              {f.label} {statusCounts[f.value] > 0 ? `(${statusCounts[f.value]})` : ''}
            </button>
          ))}
        </div>
      )}

      {isLoading && <p style={{ color: '#6b7280' }}>Loading tasks...</p>}

      {isError && (
        <div style={{ padding: 16, backgroundColor: '#fef2f2', borderRadius: 8, border: '1px solid #fecaca' }}>
          <p style={{ color: '#991b1b', fontWeight: 600, marginBottom: 4 }}>Failed to load tasks</p>
          <p style={{ color: '#b91c1c', fontSize: 13 }}>
            {error instanceof Error ? error.message : 'An unexpected error occurred.'}
          </p>
        </div>
      )}

      {data && allTasks.length === 0 && (
        <div style={{ padding: 32, textAlign: 'center', border: '1px dashed #d1d5db', borderRadius: 8 }}>
          <p style={{ fontSize: 16, color: '#374151', marginBottom: 4 }}>No tasks yet</p>
          {canCreateTask ? (
            <>
              <p style={{ fontSize: 13, color: '#6b7280', marginBottom: 16 }}>
                Create your first task to get started.
              </p>
              <Link
                href={taskNewPath(workspaceId)}
                style={{
                  display: 'inline-block',
                  padding: '8px 16px',
                  backgroundColor: '#1d4ed8',
                  color: 'white',
                  borderRadius: 6,
                  fontSize: 14,
                  fontWeight: 600,
                  textDecoration: 'none',
                }}
              >
                Create your first task
              </Link>
              <p style={{ fontSize: 13, color: '#6b7280', marginTop: 12 }}>
                Or{' '}
                <Link href={taskNewPath(workspaceId) + '?template=demo'} style={{ color: '#1d4ed8', textDecoration: 'none' }}>
                  try a demo task
                </Link>
                {' '}to see Keviq Core in action.
              </p>
            </>
          ) : (
            <p style={{ fontSize: 13, color: '#9ca3af' }}>
              Tasks will appear here once created.
            </p>
          )}
        </div>
      )}

      {filteredTasks.length > 0 && (
        <table style={{ width: '100%', borderCollapse: 'collapse' }}>
          <thead>
            <tr style={{ borderBottom: '2px solid #e5e7eb', textAlign: 'left' }}>
              <th style={{ padding: '8px 12px' }}>Title</th>
              <th style={{ padding: '8px 12px' }}>Status</th>
              <th style={{ padding: '8px 12px' }}>Run</th>
              <th style={{ padding: '8px 12px' }}>Updated</th>
            </tr>
          </thead>
          <tbody>
            {filteredTasks.map((task) => (
              <tr key={task.task_id} style={{ borderBottom: '1px solid #f3f4f6' }}>
                <td style={{ padding: '8px 12px' }}>
                  <Link
                    href={taskDetailPath(workspaceId, task.task_id)}
                    style={{ color: '#1d4ed8', textDecoration: 'none' }}
                  >
                    {task.title}
                  </Link>
                </td>
                <td style={{ padding: '8px 12px' }}>
                  <StatusBadge status={task.task_status} />
                </td>
                <td style={{ padding: '8px 12px' }}>
                  {task.latest_run_id ? (
                    <Link
                      href={runDetailPath(workspaceId, task.latest_run_id)}
                      style={{ color: '#1d4ed8', textDecoration: 'none', fontSize: 13 }}
                    >
                      View run →
                    </Link>
                  ) : (
                    <span style={{ color: '#9ca3af', fontSize: 13 }}>&mdash;</span>
                  )}
                </td>
                <td style={{ padding: '8px 12px', color: '#6b7280', fontSize: 13 }}>
                  {formatRelativeTime(task.updated_at)}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      )}

      {data && filteredTasks.length === 0 && allTasks.length > 0 && (
        <div style={{ padding: 24, textAlign: 'center', border: '1px dashed #d1d5db', borderRadius: 8 }}>
          <p style={{ fontSize: 13, color: '#6b7280' }}>No {statusFilter} tasks found.</p>
        </div>
      )}
    </div>
  );
}
