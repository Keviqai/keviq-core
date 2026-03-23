'use client';

import Link from 'next/link';
import { runDetailPath, artifactDetailPath } from '@keviq/routing';
import { formatRelativeTime, formatArtifactType } from '@/modules/shared/format-utils';

interface TaskResultBannerProps {
  taskStatus: string;
  workspaceId: string;
  latestRun: { run_id: string; run_status: string; completed_at?: string | null; error_summary?: string | null } | null;
  latestArtifact: { id: string; name: string; artifact_type: string; artifact_status: string } | null;
  previewSnippet: string;
  canViewRun: boolean;
  canRetry: boolean;
}

const BANNER_STYLES: Record<string, { border: string; bg: string }> = {
  completed: { border: '1px solid #a7f3d0', bg: '#f0fdf4' },
  failed: { border: '1px solid #fecaca', bg: '#fef2f2' },
  running: { border: '2px solid #93c5fd', bg: '#eff6ff' },
  pending: { border: '2px solid #93c5fd', bg: '#eff6ff' },
  waiting_human: { border: '1px solid #fde68a', bg: '#fffbeb' },
};

export function TaskResultBanner({
  taskStatus, workspaceId, latestRun, latestArtifact,
  previewSnippet, canViewRun, canRetry,
}: TaskResultBannerProps) {
  const styles = BANNER_STYLES[taskStatus] ?? { border: '1px solid #e5e7eb', bg: '#fff' };

  return (
    <div style={{ padding: 16, borderRadius: 8, marginBottom: 20, border: styles.border, backgroundColor: styles.bg }}>
      {/* ── Completed: result-first ── */}
      {taskStatus === 'completed' && (
        <>
          <BannerHeader icon="✓" color="#065f46"
            text={`Task completed ${latestRun?.completed_at ? formatRelativeTime(latestRun.completed_at) : ''}`}
          />
          {latestArtifact ? (
            <div>
              <p style={{ margin: 0, fontSize: 13, color: '#374151', marginBottom: 8 }}>
                Output: <strong>{latestArtifact.name}</strong>
                <span style={{ color: '#6b7280' }}> · {formatArtifactType(latestArtifact.artifact_type)} · {latestArtifact.artifact_status}</span>
              </p>
              {previewSnippet && (
                <div style={{
                  backgroundColor: '#fff', border: '1px solid #d1d5db', borderRadius: 6,
                  padding: '10px 14px', fontSize: 13, color: '#374151', lineHeight: 1.5,
                  marginBottom: 12, fontFamily: 'monospace', whiteSpace: 'pre-wrap',
                  maxHeight: 100, overflow: 'hidden',
                }}>
                  {previewSnippet}{previewSnippet.length >= 250 ? '…' : ''}
                </div>
              )}
              <div style={{ display: 'flex', gap: 8 }}>
                <PrimaryCTA href={artifactDetailPath(workspaceId, latestArtifact.id)} label="View Output →" color="#059669" />
                {canViewRun && latestRun && (
                  <SecondaryCTA href={runDetailPath(workspaceId, latestRun.run_id)} label="Run details" />
                )}
              </div>
            </div>
          ) : latestRun ? (
            <div>
              <p style={{ margin: 0, fontSize: 13, color: '#6b7280', marginBottom: 8 }}>
                Task completed but no output artifact was produced.
              </p>
              {canViewRun && (
                <PrimaryCTA href={runDetailPath(workspaceId, latestRun.run_id)} label="View Run Details →" />
              )}
            </div>
          ) : (
            <p style={{ margin: 0, fontSize: 13, color: '#9ca3af' }}>Task completed without runs.</p>
          )}
        </>
      )}

      {/* ── Running / Pending ── */}
      {(taskStatus === 'running' || taskStatus === 'pending') && (
        <>
          <BannerHeader icon="⏳" color="#1e40af"
            text={taskStatus === 'running' ? 'Agent is working...' : 'Queued, waiting to start...'}
          />
          {canViewRun && latestRun && (
            <PrimaryCTA href={runDetailPath(workspaceId, latestRun.run_id)} label="View Progress →" />
          )}
        </>
      )}

      {/* ── Failed ── */}
      {taskStatus === 'failed' && (
        <>
          <BannerHeader icon="✗" color="#991b1b"
            text={`Task failed ${latestRun?.completed_at ? formatRelativeTime(latestRun.completed_at) : ''}`}
          />
          <p style={{ margin: 0, fontSize: 13, color: '#b91c1c', marginBottom: 8 }}>
            {latestRun?.error_summary || 'The agent encountered an error while processing this task. Check the run details for more information.'}
          </p>
          <FailureRecoveryHint errorSummary={latestRun?.error_summary} />
          <div style={{ display: 'flex', gap: 8, alignItems: 'center' }}>
            {canViewRun && latestRun && (
              <PrimaryCTA href={runDetailPath(workspaceId, latestRun.run_id)} label="Inspect Run →" color="#dc2626" />
            )}
            {canRetry && <span style={{ fontSize: 13, color: '#6b7280' }}>or use Retry above</span>}
          </div>
        </>
      )}

      {/* ── Waiting human ── */}
      {taskStatus === 'waiting_human' && (
        <>
          <BannerHeader icon="🔔" color="#92400e" text="Needs your review" />
          <p style={{ margin: 0, fontSize: 13, color: '#78350f', marginBottom: 8 }}>
            The agent is waiting for human approval before continuing.
          </p>
          {canViewRun && latestRun && (
            <PrimaryCTA href={runDetailPath(workspaceId, latestRun.run_id)} label="Review Now →" color="#d97706" />
          )}
        </>
      )}
    </div>
  );
}

function BannerHeader({ icon, color, text }: { icon: string; color: string; text: string }) {
  return (
    <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 8 }}>
      <span style={{ fontSize: 18 }}>{icon}</span>
      <h3 style={{ fontSize: 15, fontWeight: 600, margin: 0, color }}>{text}</h3>
    </div>
  );
}

function PrimaryCTA({ href, label, color = '#1d4ed8' }: { href: string; label: string; color?: string }) {
  return (
    <Link href={href} style={{
      display: 'inline-flex', alignItems: 'center', gap: 6, padding: '8px 20px',
      backgroundColor: color, color: 'white', borderRadius: 6,
      textDecoration: 'none', fontSize: 14, fontWeight: 600,
    }}>
      {label}
    </Link>
  );
}

function SecondaryCTA({ href, label }: { href: string; label: string }) {
  return (
    <Link href={href} style={{
      display: 'inline-flex', alignItems: 'center', gap: 6, padding: '8px 16px',
      backgroundColor: '#fff', color: '#374151', border: '1px solid #d1d5db',
      borderRadius: 6, textDecoration: 'none', fontSize: 13, fontWeight: 500,
    }}>
      {label}
    </Link>
  );
}

function FailureRecoveryHint({ errorSummary }: { errorSummary?: string | null }) {
  if (!errorSummary) return null;
  const lower = errorSummary.toLowerCase();

  let hint: string | null = null;
  if (lower.includes('provider') || lower.includes('model alias') || lower.includes('not configured')) {
    hint = 'This usually means the AI model provider is not set up. Ask your system administrator to verify the model provider configuration.';
  } else if (lower.includes('bridge') || lower.includes('cannot connect') || lower.includes('not reachable')) {
    hint = 'The AI model service appears to be offline. Please ensure it is running, then click Retry above.';
  } else if (lower.includes('timed out') || lower.includes('timeout') || lower.includes('too long')) {
    hint = 'The model took too long to respond. Try again — if it persists, try simplifying the task brief.';
  } else if (lower.includes('internal server error') || lower.includes('http 500')) {
    hint = 'An internal error occurred. This is typically temporary. Try again after a moment.';
  }

  if (!hint) return null;
  return (
    <p style={{ margin: '0 0 8px', fontSize: 12, color: '#6b7280', fontStyle: 'italic' }}>
      {hint}
    </p>
  );
}
