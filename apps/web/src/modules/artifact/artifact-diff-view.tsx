'use client';

import { useMemo } from 'react';
import type { ArtifactPreviewResponse } from '@keviq/api-client';
import { computeDiff, getDiffStats, prepareContent } from './text-diff';

const DIFFABLE_KINDS = new Set(['text', 'markdown', 'json']);

const LINE_STYLE: Record<string, React.CSSProperties> = {
  add: { backgroundColor: '#f0fdf4', borderLeft: '3px solid #16a34a' },
  remove: { backgroundColor: '#fef2f2', borderLeft: '3px solid #dc2626' },
  same: { backgroundColor: 'transparent', borderLeft: '3px solid transparent' },
};

const LINE_PREFIX: Record<string, string> = { add: '+', remove: '−', same: ' ' };
const PREFIX_COLOR: Record<string, string> = { add: '#16a34a', remove: '#dc2626', same: '#9ca3af' };

export function ArtifactDiffView({
  currentPreview,
  parentPreview,
  currentVersionLabel,
  parentVersionLabel,
  isLoading,
  isError,
}: {
  currentPreview: ArtifactPreviewResponse | null | undefined;
  parentPreview: ArtifactPreviewResponse | null | undefined;
  currentVersionLabel: string;
  parentVersionLabel: string;
  isLoading: boolean;
  isError: boolean;
}) {
  const diffResult = useMemo(() => {
    if (!currentPreview?.content || !parentPreview?.content) return null;
    const kind = currentPreview.preview_kind;
    if (!DIFFABLE_KINDS.has(kind)) return null;

    const a = prepareContent(parentPreview.content, kind);
    const b = prepareContent(currentPreview.content, kind);
    return computeDiff(a, b);
  }, [currentPreview, parentPreview]);

  if (isLoading) {
    return <p style={{ color: '#9ca3af', fontSize: 13 }}>Loading diff...</p>;
  }

  if (isError) {
    return (
      <div style={{ padding: 12, backgroundColor: '#fef2f2', borderRadius: 6, border: '1px solid #fecaca' }}>
        <p style={{ color: '#b91c1c', fontSize: 13, margin: 0 }}>Failed to load content for comparison.</p>
      </div>
    );
  }

  if (!currentPreview || !parentPreview) {
    return <p style={{ color: '#9ca3af', fontSize: 13 }}>Waiting for content...</p>;
  }

  const kind = currentPreview.preview_kind;

  if (!DIFFABLE_KINDS.has(kind)) {
    return (
      <div style={{ padding: 16, backgroundColor: '#f9fafb', borderRadius: 6, border: '1px solid #e5e7eb', textAlign: 'center' }}>
        <p style={{ color: '#6b7280', fontSize: 13, margin: 0 }}>
          Diff not available for <strong>{kind}</strong> content.
          {kind === 'unsupported' && ' Download both versions to compare.'}
          {kind === 'too_large' && ' File too large to diff in browser.'}
        </p>
      </div>
    );
  }

  if (diffResult === null) {
    return (
      <div style={{ padding: 16, backgroundColor: '#f9fafb', borderRadius: 6, border: '1px solid #e5e7eb', textAlign: 'center' }}>
        <p style={{ color: '#6b7280', fontSize: 13, margin: 0 }}>
          Content too large to diff in browser (exceeds 800 lines per side).
          Download both versions to compare.
        </p>
      </div>
    );
  }

  const stats = getDiffStats(diffResult);

  return (
    <div>
      {/* Header */}
      <div style={{ display: 'flex', gap: 16, marginBottom: 12, alignItems: 'center', flexWrap: 'wrap' }}>
        <div style={{ display: 'flex', gap: 8, alignItems: 'center' }}>
          <span style={{ fontSize: 13, padding: '2px 8px', backgroundColor: '#fef2f2', color: '#dc2626', borderRadius: 4, fontFamily: 'monospace' }}>
            − {parentVersionLabel}
          </span>
          <span style={{ color: '#9ca3af' }}>→</span>
          <span style={{ fontSize: 13, padding: '2px 8px', backgroundColor: '#f0fdf4', color: '#16a34a', borderRadius: 4, fontFamily: 'monospace' }}>
            + {currentVersionLabel}
          </span>
        </div>
        {stats.changed ? (
          <span style={{ fontSize: 12, color: '#6b7280' }}>
            <span style={{ color: '#16a34a', fontWeight: 600 }}>+{stats.added}</span>
            {' / '}
            <span style={{ color: '#dc2626', fontWeight: 600 }}>−{stats.removed}</span>
            {' lines'}
          </span>
        ) : (
          <span style={{ fontSize: 12, color: '#6b7280', fontStyle: 'italic' }}>No differences</span>
        )}
        {kind === 'markdown' && (
          <span style={{ fontSize: 11, color: '#9ca3af' }}>Diffing raw source</span>
        )}
      </div>

      {/* Diff lines */}
      <div style={{
        fontFamily: 'monospace',
        fontSize: 12,
        lineHeight: 1.5,
        border: '1px solid #e5e7eb',
        borderRadius: 6,
        overflow: 'auto',
        maxHeight: 560,
        backgroundColor: '#fff',
      }}>
        {diffResult.map((line, idx) => (
          <div
            key={`${line.type}-${idx}`}
            style={{ display: 'flex', ...LINE_STYLE[line.type], minWidth: '100%' }}
          >
            <span style={{
              width: 20, flexShrink: 0, textAlign: 'center',
              color: PREFIX_COLOR[line.type], userSelect: 'none', paddingLeft: 4,
            }}>
              {LINE_PREFIX[line.type]}
            </span>
            <span style={{
              whiteSpace: 'pre-wrap', wordBreak: 'break-all', padding: '0 8px',
              color: line.type === 'same' ? '#374151' : 'inherit',
            }}>
              {line.text || '\u00a0'}
            </span>
          </div>
        ))}
      </div>
    </div>
  );
}
