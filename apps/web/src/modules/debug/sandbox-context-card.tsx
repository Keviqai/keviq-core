'use client';

import { useSandboxDetail } from '@keviq/server-state';

/**
 * SandboxContextCard — compact read-only card showing sandbox identity,
 * status, type, and lifecycle timestamps.
 *
 * Designed to appear inside ToolExecutionViewer or on run detail page.
 * Not a management UI — purely informational context for investigation.
 */

interface SandboxContextCardProps {
  sandboxId: string;
}

const STATUS_COLORS: Record<string, string> = {
  provisioning: '#2563eb',
  ready: '#059669',
  executing: '#d97706',
  idle: '#059669',
  terminating: '#6b7280',
  terminated: '#6b7280',
  failed: '#dc2626',
};

function formatTimestamp(iso: string | null): string {
  if (!iso) return '-';
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return '-';
  return d.toLocaleString(undefined, {
    month: 'short', day: 'numeric',
    hour: '2-digit', minute: '2-digit', second: '2-digit',
  });
}

export function SandboxContextCard({ sandboxId }: SandboxContextCardProps) {
  const { data, isLoading, isError } = useSandboxDetail(sandboxId);

  if (isLoading) {
    return <p style={{ fontSize: 12, color: '#9ca3af' }}>Loading sandbox...</p>;
  }

  if (isError || !data) {
    return (
      <div style={cardStyle}>
        <span style={{ fontSize: 12, color: '#9ca3af' }}>
          Sandbox {sandboxId.slice(0, 8)}... (details unavailable)
        </span>
      </div>
    );
  }

  const statusColor = STATUS_COLORS[data.sandbox_status] ?? '#6b7280';

  return (
    <div style={cardStyle}>
      <div style={{ fontSize: 12, fontWeight: 600, color: '#374151', marginBottom: 6, display: 'flex', alignItems: 'center', gap: 8 }}>
        Sandbox
        <span style={{
          fontSize: 10, fontWeight: 600, padding: '1px 6px', borderRadius: 3,
          backgroundColor: statusColor + '15', color: statusColor,
        }}>
          {data.sandbox_status.toUpperCase()}
        </span>
        <span style={{ fontSize: 10, color: '#6b7280', fontWeight: 400 }}>
          {data.sandbox_type}
        </span>
      </div>
      <div style={{ display: 'grid', gridTemplateColumns: '90px 1fr', gap: '3px 10px', fontSize: 12 }}>
        <span style={labelStyle}>ID</span>
        <span style={valueStyle}>{data.sandbox_id.slice(0, 12)}...</span>

        <span style={labelStyle}>Created</span>
        <span style={valueStyle}>{formatTimestamp(data.created_at)}</span>

        {data.started_at && (
          <>
            <span style={labelStyle}>Started</span>
            <span style={valueStyle}>{formatTimestamp(data.started_at)}</span>
          </>
        )}

        {data.terminated_at && (
          <>
            <span style={labelStyle}>Terminated</span>
            <span style={valueStyle}>{formatTimestamp(data.terminated_at)}</span>
          </>
        )}

        {data.termination_reason && (
          <>
            <span style={labelStyle}>Reason</span>
            <span style={valueStyle}>{data.termination_reason}</span>
          </>
        )}
      </div>
    </div>
  );
}

const cardStyle: React.CSSProperties = {
  border: '1px solid #e5e7eb',
  borderRadius: 6,
  padding: 10,
  backgroundColor: '#f9fafb',
  marginBottom: 12,
};

const labelStyle: React.CSSProperties = {
  color: '#6b7280',
  fontWeight: 500,
};

const valueStyle: React.CSSProperties = {
  color: '#111827',
  fontFamily: 'inherit',
};
