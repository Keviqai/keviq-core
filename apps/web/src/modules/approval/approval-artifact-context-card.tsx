'use client';

import Link from 'next/link';
import type { ArtifactContextSummary } from '@keviq/domain-types';
import { artifactDetailPath } from '@keviq/routing';

interface ApprovalArtifactContextCardProps {
  workspaceId: string;
  artifactId: string;
  context: ArtifactContextSummary | null | undefined;
}

function formatBytes(bytes: number | null): string {
  if (bytes === null || bytes === undefined) return '—';
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
}

export function ApprovalArtifactContextCard({
  workspaceId,
  artifactId,
  context,
}: ApprovalArtifactContextCardProps) {
  const artifactLink = artifactDetailPath(workspaceId, artifactId);

  return (
    <div style={{
      border: '1px solid #e5e7eb',
      borderRadius: 8,
      padding: 16,
      marginBottom: 20,
      backgroundColor: '#f9fafb',
    }}>
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 12 }}>
        <h3 style={{ fontSize: 14, fontWeight: 600, color: '#374151', margin: 0 }}>
          Artifact under review
        </h3>
        <Link
          href={artifactLink}
          style={{
            fontSize: 13,
            color: '#1d4ed8',
            textDecoration: 'none',
            fontWeight: 500,
          }}
        >
          View artifact →
        </Link>
      </div>

      {!context ? (
        <p style={{ fontSize: 13, color: '#9ca3af', margin: 0 }}>
          Artifact context unavailable.{' '}
          <Link href={artifactLink} style={{ color: '#1d4ed8', textDecoration: 'none' }}>
            Open artifact directly →
          </Link>
        </p>
      ) : (
        <dl style={{ margin: 0, display: 'grid', gridTemplateColumns: '130px 1fr', gap: '6px 12px' }}>
          <dt style={{ fontSize: 12, color: '#6b7280', fontWeight: 500 }}>Name</dt>
          <dd style={{ margin: 0, fontSize: 13, color: '#111827', fontWeight: 500 }}>
            {context.name ?? '—'}
          </dd>

          <dt style={{ fontSize: 12, color: '#6b7280', fontWeight: 500 }}>Type</dt>
          <dd style={{ margin: 0 }}>
            {context.artifact_type ? (
              <span style={{
                display: 'inline-block',
                padding: '1px 8px',
                backgroundColor: '#dbeafe',
                color: '#1e40af',
                borderRadius: 4,
                fontSize: 11,
                fontWeight: 600,
                textTransform: 'uppercase',
                letterSpacing: '0.05em',
              }}>
                {context.artifact_type.replace(/_/g, ' ')}
              </span>
            ) : '—'}
          </dd>

          <dt style={{ fontSize: 12, color: '#6b7280', fontWeight: 500 }}>Status</dt>
          <dd style={{ margin: 0, fontSize: 13, color: '#374151' }}>
            {context.artifact_status ?? '—'}
          </dd>

          <dt style={{ fontSize: 12, color: '#6b7280', fontWeight: 500 }}>Size</dt>
          <dd style={{ margin: 0, fontSize: 13, color: '#374151' }}>
            {formatBytes(context.size_bytes)}
          </dd>

          <dt style={{ fontSize: 12, color: '#6b7280', fontWeight: 500 }}>Annotations</dt>
          <dd style={{ margin: 0, fontSize: 13, color: '#374151' }}>
            {context.annotation_count !== null && context.annotation_count !== undefined
              ? `${context.annotation_count} annotation${context.annotation_count !== 1 ? 's' : ''}`
              : '—'}
          </dd>
        </dl>
      )}
    </div>
  );
}
