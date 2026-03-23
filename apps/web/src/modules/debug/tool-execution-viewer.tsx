'use client';

import { useToolExecution } from '@keviq/server-state';
import { SandboxContextCard } from './sandbox-context-card';

/**
 * ToolExecutionViewer — displays full execution detail for a single tool run.
 *
 * Shows: tool_name, tool_input, stdout, stderr, exit_code, status,
 * duration, truncation indicator. Designed as an inline expandable panel,
 * not a separate page.
 */

interface ToolExecutionViewerProps {
  executionId: string;
  onClose?: () => void;
}

function formatMs(ms: number): string {
  if (ms < 1000) return `${ms}ms`;
  if (ms < 60000) return `${(ms / 1000).toFixed(1)}s`;
  return `${(ms / 60000).toFixed(1)}min`;
}

const STATUS_COLORS: Record<string, string> = {
  completed: '#059669',
  failed: '#dc2626',
  timed_out: '#d97706',
  pending: '#6b7280',
  running: '#2563eb',
};

export function ToolExecutionViewer({ executionId, onClose }: ToolExecutionViewerProps) {
  const { data, isLoading, isError, error } = useToolExecution(executionId);

  if (isLoading) {
    return (
      <div style={containerStyle}>
        <p style={{ color: '#6b7280', fontSize: 13 }}>Loading execution detail...</p>
      </div>
    );
  }

  if (isError || !data) {
    return (
      <div style={containerStyle}>
        <p style={{ color: '#991b1b', fontSize: 13 }}>
          {error instanceof Error ? error.message : 'Failed to load execution detail'}
        </p>
        {onClose && <button onClick={onClose} style={closeBtnStyle}>Close</button>}
      </div>
    );
  }

  const statusColor = STATUS_COLORS[data.status] ?? '#6b7280';
  const duration = data.started_at && data.completed_at
    ? new Date(data.completed_at).getTime() - new Date(data.started_at).getTime()
    : null;

  return (
    <div style={containerStyle}>
      {/* Header */}
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 12 }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
          <h4 style={{ fontSize: 14, fontWeight: 600, margin: 0, color: '#111827' }}>
            {data.tool_name}
          </h4>
          <span style={{
            fontSize: 11, fontWeight: 600, padding: '2px 8px', borderRadius: 4,
            backgroundColor: statusColor + '15', color: statusColor,
          }}>
            {data.status.toUpperCase()}
          </span>
          {data.exit_code !== null && (
            <span style={{ fontSize: 11, color: '#6b7280' }}>exit {data.exit_code}</span>
          )}
          {duration !== null && (
            <span style={{ fontSize: 11, color: '#6b7280' }}>{formatMs(duration)}</span>
          )}
          {data.truncated && (
            <span style={{
              fontSize: 10, fontWeight: 500, padding: '1px 6px', borderRadius: 3,
              backgroundColor: '#fef3c7', color: '#92400e',
            }}>
              TRUNCATED
            </span>
          )}
        </div>
        {onClose && <button onClick={onClose} style={closeBtnStyle}>Close</button>}
      </div>

      {/* Sandbox context */}
      {data.sandbox_id && <SandboxContextCard sandboxId={data.sandbox_id} />}

      {/* Tool input */}
      {data.tool_input && Object.keys(data.tool_input).length > 0 && (
        <Section title="Input">
          <pre style={preStyle}>{JSON.stringify(data.tool_input, null, 2)}</pre>
        </Section>
      )}

      {/* Stdout */}
      {data.stdout && (
        <Section title="stdout">
          <pre style={preStyle}>{data.stdout}</pre>
        </Section>
      )}

      {/* Stderr */}
      {data.stderr && (
        <Section title="stderr">
          <pre style={{ ...preStyle, backgroundColor: '#fef2f2', borderColor: '#fecaca', color: '#991b1b' }}>
            {data.stderr}
          </pre>
        </Section>
      )}

      {/* Error detail */}
      {data.error_detail && (
        <Section title="Error">
          <pre style={{ ...preStyle, backgroundColor: '#fef2f2', borderColor: '#fecaca', color: '#991b1b' }}>
            {JSON.stringify(data.error_detail, null, 2)}
          </pre>
        </Section>
      )}

      {/* No output */}
      {!data.stdout && !data.stderr && !data.error_detail && (
        <p style={{ fontSize: 12, color: '#9ca3af', fontStyle: 'italic' }}>No output recorded.</p>
      )}
    </div>
  );
}

function Section({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <div style={{ marginBottom: 12 }}>
      <div style={{ fontSize: 11, fontWeight: 600, color: '#6b7280', marginBottom: 4, textTransform: 'uppercase', letterSpacing: 0.5 }}>
        {title}
      </div>
      {children}
    </div>
  );
}

const containerStyle: React.CSSProperties = {
  border: '1px solid #e5e7eb',
  borderRadius: 8,
  padding: 16,
  marginTop: 8,
  marginBottom: 8,
  backgroundColor: '#fafafa',
};

const preStyle: React.CSSProperties = {
  margin: 0,
  padding: 10,
  fontSize: 12,
  fontFamily: 'monospace',
  backgroundColor: '#f3f4f6',
  border: '1px solid #e5e7eb',
  borderRadius: 6,
  whiteSpace: 'pre-wrap',
  wordBreak: 'break-word',
  maxHeight: 400,
  overflow: 'auto',
};

const closeBtnStyle: React.CSSProperties = {
  fontSize: 12,
  color: '#6b7280',
  background: 'none',
  border: '1px solid #d1d5db',
  borderRadius: 4,
  padding: '2px 10px',
  cursor: 'pointer',
};
