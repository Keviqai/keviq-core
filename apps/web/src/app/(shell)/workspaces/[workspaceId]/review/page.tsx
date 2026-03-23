'use client';

import { useState, useMemo } from 'react';
import Link from 'next/link';
import { useParams } from 'next/navigation';
import { useApprovalList, useMembers } from '@keviq/server-state';
import { approvalDetailPath, taskDetailPath, workspacePath } from '@keviq/routing';
import { StatusBadge } from '@/modules/shared/status-badge';
import { resolveDisplayName } from '@/modules/approval/member-display';

/**
 * Shared Review Queue — aggregates pending items needing team action.
 *
 * P6-S4: Shows pending approvals (artifact + tool_call) in one unified view.
 * Queue inclusion: all pending approvals for this workspace.
 * Future: could add failed tasks/runs needing triage.
 */

const QUEUE_FILTERS = [
  { label: 'All', value: '' },
  { label: 'Artifact approvals', value: 'artifact' },
  { label: 'Tool approvals', value: 'tool_call' },
] as const;

function formatAge(iso: string): string {
  const diff = Date.now() - new Date(iso).getTime();
  const mins = Math.floor(diff / 60_000);
  if (mins < 1) return 'just now';
  if (mins < 60) return `${mins}m ago`;
  const hrs = Math.floor(mins / 60);
  if (hrs < 24) return `${hrs}h ago`;
  return `${Math.floor(hrs / 24)}d ago`;
}

export default function ReviewQueuePage() {
  const params = useParams<{ workspaceId: string }>();
  const workspaceId = params.workspaceId;
  const [typeFilter, setTypeFilter] = useState('');

  const { data, isLoading, isError, error } = useApprovalList(workspaceId, 'pending');
  const { data: members } = useMembers(workspaceId);

  const items = useMemo(() => {
    const approvals = data?.items ?? [];
    if (!typeFilter) return approvals;
    return approvals.filter(a => a.target_type === typeFilter);
  }, [data, typeFilter]);

  return (
    <div>
      <div style={{ marginBottom: 8 }}>
        <Link href={workspacePath(workspaceId)} style={{ color: '#6b7280', fontSize: 13, textDecoration: 'none' }}>
          &larr; Overview
        </Link>
      </div>

      <div style={{ marginBottom: 16 }}>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
          <h1 style={{ fontSize: 24, fontWeight: 700, margin: 0 }}>
            Needs Review
            {items.length > 0 && (
              <span style={{ fontWeight: 400, fontSize: 16, color: '#d97706', marginLeft: 8 }}>
                ({items.length})
              </span>
            )}
          </h1>
        </div>
        <p style={{ fontSize: 13, color: '#6b7280', margin: '4px 0 0' }}>Items waiting for your decision right now.</p>
      </div>

      {/* Filters */}
      <div style={{ display: 'flex', gap: 8, marginBottom: 16 }}>
        {QUEUE_FILTERS.map(f => (
          <button
            key={f.value}
            onClick={() => setTypeFilter(f.value)}
            style={{
              padding: '6px 12px', fontSize: 13, borderRadius: 6, cursor: 'pointer',
              border: typeFilter === f.value ? '1px solid #1d4ed8' : '1px solid #d1d5db',
              backgroundColor: typeFilter === f.value ? '#eff6ff' : '#fff',
              color: typeFilter === f.value ? '#1d4ed8' : '#374151',
              fontWeight: typeFilter === f.value ? 600 : 400,
            }}
          >
            {f.label}
          </button>
        ))}
      </div>

      {/* Loading / Error */}
      {isLoading && <p style={{ color: '#6b7280' }}>Loading review queue...</p>}
      {isError && (
        <p style={{ color: '#b91c1c', fontSize: 13 }}>
          {error instanceof Error ? error.message : 'Failed to load review queue'}
        </p>
      )}

      {/* Empty state */}
      {!isLoading && items.length === 0 && (
        <div style={{ padding: 32, textAlign: 'center', border: '2px dashed #d1d5db', borderRadius: 8 }}>
          <p style={{ fontSize: 14, color: '#059669', fontWeight: 600, marginBottom: 4 }}>All clear</p>
          <p style={{ fontSize: 13, color: '#6b7280', margin: 0 }}>No items need review right now.</p>
        </div>
      )}

      {/* Queue items */}
      {items.length > 0 && (
        <div style={{ border: '1px solid #e5e7eb', borderRadius: 8, overflow: 'hidden' }}>
          {items.map(item => (
            <Link
              key={item.approval_id}
              href={approvalDetailPath(workspaceId, item.approval_id)}
              style={{ textDecoration: 'none', color: 'inherit', display: 'block' }}
            >
              <div style={{
                padding: '12px 16px', borderBottom: '1px solid #f3f4f6',
                display: 'flex', alignItems: 'center', gap: 12,
                cursor: 'pointer',
              }}>
                {/* Type badge */}
                <span style={{
                  fontSize: 10, fontWeight: 600, padding: '2px 8px', borderRadius: 4,
                  backgroundColor: item.target_type === 'tool_call' ? '#fef3c7' : '#eff6ff',
                  color: item.target_type === 'tool_call' ? '#92400e' : '#1d4ed8',
                  whiteSpace: 'nowrap',
                }}>
                  {item.target_type === 'tool_call' ? 'TOOL' : 'ARTIFACT'}
                </span>

                {/* Content */}
                <div style={{ flex: 1, minWidth: 0 }}>
                  <div style={{ fontSize: 13, fontWeight: 500, color: '#111827' }}>
                    {item.target_type === 'tool_call' && item.tool_context
                      ? `Tool: ${item.tool_context.tool_name}`
                      : item.artifact_name
                        ? `Artifact: ${item.artifact_name}`
                        : `${item.target_type}: ${item.target_id.slice(0, 8)}...`
                    }
                  </div>
                  {item.prompt && (
                    <div style={{ fontSize: 12, color: '#6b7280', marginTop: 2 }}>
                      {item.prompt.slice(0, 100)}{item.prompt.length > 100 ? '...' : ''}
                    </div>
                  )}
                </div>

                {/* Requester + age */}
                <div style={{ textAlign: 'right', flexShrink: 0 }}>
                  <div style={{ fontSize: 12, color: '#6b7280' }}>
                    {resolveDisplayName(item.requested_by, members)}
                  </div>
                  <div style={{ fontSize: 11, color: '#9ca3af' }}>
                    {formatAge(item.created_at)}
                  </div>
                </div>

                {/* Status */}
                <StatusBadge status={item.decision} />
              </div>
            </Link>
          ))}
        </div>
      )}
    </div>
  );
}
