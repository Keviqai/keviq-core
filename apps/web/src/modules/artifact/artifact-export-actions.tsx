'use client';

import { useState } from 'react';
import { useArtifactPreview } from '@keviq/server-state';
import { artifactDetailPath } from '@keviq/routing';

const EXPORTABLE_KINDS = new Set(['text', 'markdown', 'json']);

interface ExportMeta {
  ext: string;
  mime: string;
  label: string;
}

function getExportMeta(previewKind: string): ExportMeta | null {
  if (previewKind === 'markdown') return { ext: 'md', mime: 'text/markdown', label: 'Export .md' };
  if (previewKind === 'json') return { ext: 'json', mime: 'application/json', label: 'Export .json' };
  if (previewKind === 'text') return { ext: 'txt', mime: 'text/plain', label: 'Export .txt' };
  return null;
}

function sanitizeFilename(name: string): string {
  return name.replace(/[^a-z0-9_\-. ]/gi, '_').trim() || 'artifact';
}

function triggerDownload(content: string, filename: string, mimeType: string): void {
  const blob = new Blob([content], { type: mimeType });
  const url = URL.createObjectURL(blob);
  const a = document.createElement('a');
  a.href = url;
  a.download = filename;
  document.body.appendChild(a);
  a.click();
  document.body.removeChild(a);
  URL.revokeObjectURL(url);
}

export function ArtifactExportActions({
  workspaceId,
  artifactId,
  artifactName,
  artifactStatus,
}: {
  workspaceId: string;
  artifactId: string;
  artifactName: string;
  artifactStatus: string;
}) {
  const [linkState, setLinkState] = useState<'idle' | 'copied'>('idle');
  const [exportState, setExportState] = useState<'idle' | 'done' | 'error'>('idle');

  const isReady = artifactStatus === 'ready';
  const { data: preview } = useArtifactPreview(workspaceId, isReady ? artifactId : '');

  function handleCopyLink() {
    const url = `${window.location.origin}${artifactDetailPath(workspaceId, artifactId)}`;
    navigator.clipboard.writeText(url).then(() => {
      setLinkState('copied');
      setTimeout(() => setLinkState('idle'), 2000);
    }).catch(() => {
      // clipboard write failed (permissions denied or non-secure context) — stay idle
    });
  }

  function handleExport() {
    if (exportState !== 'idle') return; // prevent double-click / stacked timers
    if (!preview?.content || !preview.preview_kind) return;
    const meta = getExportMeta(preview.preview_kind);
    if (!meta) return;

    let content = preview.content;
    if (preview.preview_kind === 'json') {
      try {
        content = JSON.stringify(JSON.parse(content), null, 2);
      } catch {
        setExportState('error');
        setTimeout(() => setExportState('idle'), 3000);
        return;
      }
    }

    const filename = `${sanitizeFilename(artifactName)}.${meta.ext}`;
    try {
      triggerDownload(content, filename, meta.mime);
      setExportState('done');
      setTimeout(() => setExportState('idle'), 2000);
    } catch {
      setExportState('error');
      setTimeout(() => setExportState('idle'), 3000);
    }
  }

  const exportMeta = isReady && preview?.preview_kind && EXPORTABLE_KINDS.has(preview.preview_kind)
    ? getExportMeta(preview.preview_kind)
    : null;

  const btnBase: React.CSSProperties = {
    fontSize: 13, padding: '5px 12px',
    border: '1px solid #d1d5db', borderRadius: 6,
    cursor: 'pointer', whiteSpace: 'nowrap',
  };

  return (
    <div style={{ display: 'flex', gap: 8, alignItems: 'center', flexWrap: 'wrap' }}>
      <button
        type="button"
        onClick={handleCopyLink}
        style={{
          ...btnBase,
          backgroundColor: linkState === 'copied' ? '#f0fdf4' : '#f9fafb',
          color: linkState === 'copied' ? '#16a34a' : '#374151',
        }}
      >
        {linkState === 'copied' ? '✓ Link copied' : 'Copy link'}
      </button>

      {exportMeta && (
        <button
          type="button"
          onClick={handleExport}
          disabled={!preview?.content}
          style={{
            ...btnBase,
            backgroundColor: exportState === 'done' ? '#f0fdf4' : '#f9fafb',
            color: exportState === 'done'
              ? '#16a34a'
              : exportState === 'error'
              ? '#b91c1c'
              : '#374151',
            cursor: preview?.content ? 'pointer' : 'not-allowed',
            opacity: !preview?.content ? 0.5 : 1,
          }}
        >
          {exportState === 'done'
            ? '✓ Exported'
            : exportState === 'error'
            ? 'Export failed'
            : exportMeta.label}
        </button>
      )}
    </div>
  );
}
