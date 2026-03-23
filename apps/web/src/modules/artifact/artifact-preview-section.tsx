'use client';

import { useState } from 'react';
import dynamic from 'next/dynamic';
import { useArtifactPreview, useArtifactDownloadUrl } from '@keviq/server-state';
import { formatSize } from '@/modules/shared/format-utils';
import remarkGfm from 'remark-gfm';

const ReactMarkdown = dynamic(() => import('react-markdown'), { ssr: false });

const tableStyle: React.CSSProperties = { borderCollapse: 'collapse', width: '100%', fontSize: 13, margin: '8px 0' };
const thStyle: React.CSSProperties = { border: '1px solid #d1d5db', padding: '6px 10px', backgroundColor: '#f3f4f6', textAlign: 'left', fontWeight: 600 };
const tdStyle: React.CSSProperties = { border: '1px solid #d1d5db', padding: '6px 10px' };

const mdComponents = {
  table: (props: React.HTMLAttributes<HTMLTableElement>) => <table style={tableStyle} {...props} />,
  th: (props: React.HTMLAttributes<HTMLTableCellElement>) => <th style={thStyle} {...props} />,
  td: (props: React.HTMLAttributes<HTMLTableCellElement>) => <td style={tdStyle} {...props} />,
};

function CopyButton({ text }: { text: string }) {
  const [copied, setCopied] = useState(false);

  function handleCopy() {
    navigator.clipboard.writeText(text).then(() => {
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    });
  }

  return (
    <button
      type="button"
      onClick={handleCopy}
      style={{
        fontSize: 12, padding: '3px 10px',
        border: '1px solid #d1d5db', borderRadius: 5,
        backgroundColor: copied ? '#f0fdf4' : '#f9fafb',
        color: copied ? '#16a34a' : '#374151',
        cursor: 'pointer',
      }}
    >
      {copied ? '✓ Copied' : 'Copy'}
    </button>
  );
}

export function ArtifactPreviewSection({ workspaceId, artifactId, isReady }: {
  workspaceId: string;
  artifactId: string;
  isReady: boolean;
}) {
  const [rawMode, setRawMode] = useState(false);
  const { data: preview, isLoading, isError } = useArtifactPreview(workspaceId, artifactId);
  const downloadUrl = useArtifactDownloadUrl(workspaceId, artifactId);

  if (!isReady) {
    return <p style={{ color: '#9ca3af', fontSize: 13 }}>Preview available when artifact is ready.</p>;
  }

  if (isLoading) {
    return <p style={{ color: '#9ca3af', fontSize: 13 }}>Loading preview...</p>;
  }

  if (isError || !preview) {
    return <p style={{ color: '#b91c1c', fontSize: 13 }}>Failed to load preview.</p>;
  }

  if (preview.preview_kind === 'unavailable') {
    return (
      <div style={{ textAlign: 'center', padding: 24 }}>
        <p style={{ color: '#6b7280', fontSize: 13, marginBottom: 4 }}>
          Content not available for preview.
        </p>
        <p style={{ color: '#9ca3af', fontSize: 12 }}>
          This artifact was created with an older storage format.
          Re-run the task to generate a new version with inline preview.
        </p>
      </div>
    );
  }

  if (preview.preview_kind === 'unsupported') {
    return (
      <div style={{ textAlign: 'center', padding: 24 }}>
        <p style={{ color: '#6b7280', fontSize: 13, marginBottom: 8 }}>
          Preview not available for {preview.mime_type ?? 'this file type'}.
        </p>
        <a
          href={downloadUrl}
          download
          style={{ padding: '6px 16px', backgroundColor: '#1d4ed8', color: '#fff', borderRadius: 6, textDecoration: 'none', fontSize: 13 }}
        >
          Download instead
        </a>
      </div>
    );
  }

  if (preview.preview_kind === 'too_large') {
    return (
      <div style={{ textAlign: 'center', padding: 24 }}>
        <p style={{ color: '#6b7280', fontSize: 13, marginBottom: 8 }}>
          File too large to preview ({formatSize(preview.size_bytes)}).
        </p>
        <a
          href={downloadUrl}
          download
          style={{ padding: '6px 16px', backgroundColor: '#1d4ed8', color: '#fff', borderRadius: 6, textDecoration: 'none', fontSize: 13 }}
        >
          Download instead
        </a>
      </div>
    );
  }

  const content = preview.content ?? '';

  if (preview.preview_kind === 'json') {
    let formatted = content;
    try { formatted = JSON.stringify(JSON.parse(content), null, 2); } catch { /* use raw */ }
    return (
      <div>
        <div style={{ display: 'flex', justifyContent: 'flex-end', marginBottom: 6 }}>
          <CopyButton text={formatted} />
        </div>
        {preview.truncated && (
          <p style={{ color: '#d97706', fontSize: 12, marginBottom: 8 }}>Content truncated (file exceeds 1 MB preview limit).</p>
        )}
        <pre style={{
          margin: 0, padding: 12, backgroundColor: '#f9fafb', borderRadius: 6,
          fontSize: 12, fontFamily: 'monospace', whiteSpace: 'pre-wrap',
          wordBreak: 'break-all', maxHeight: 600, overflow: 'auto',
        }}>
          {formatted}
        </pre>
      </div>
    );
  }

  if (preview.preview_kind === 'markdown') {
    return (
      <div>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 6 }}>
          <div style={{ display: 'flex', gap: 4 }}>
            <button
              type="button"
              onClick={() => setRawMode(false)}
              style={{
                fontSize: 12, padding: '3px 10px',
                border: '1px solid #d1d5db', borderRadius: '5px 0 0 5px',
                backgroundColor: !rawMode ? '#1d4ed8' : '#f9fafb',
                color: !rawMode ? '#fff' : '#374151',
                cursor: 'pointer',
              }}
            >
              Rendered
            </button>
            <button
              type="button"
              onClick={() => setRawMode(true)}
              style={{
                fontSize: 12, padding: '3px 10px',
                border: '1px solid #d1d5db', borderRadius: '0 5px 5px 0',
                backgroundColor: rawMode ? '#1d4ed8' : '#f9fafb',
                color: rawMode ? '#fff' : '#374151',
                cursor: 'pointer',
              }}
            >
              Raw
            </button>
          </div>
          <CopyButton text={content} />
        </div>
        {preview.truncated && (
          <p style={{ color: '#d97706', fontSize: 12, marginBottom: 8 }}>Content truncated (file exceeds 1 MB preview limit).</p>
        )}
        {rawMode ? (
          <pre style={{
            margin: 0, padding: 12, backgroundColor: '#f9fafb', borderRadius: 6,
            fontSize: 12, fontFamily: 'monospace', whiteSpace: 'pre-wrap',
            wordBreak: 'break-all', maxHeight: 600, overflow: 'auto',
          }}>
            {content}
          </pre>
        ) : (
          <div style={{
            padding: 12, backgroundColor: '#f9fafb', borderRadius: 6,
            fontSize: 14, lineHeight: 1.6, maxHeight: 600, overflow: 'auto',
          }}>
            <ReactMarkdown remarkPlugins={[remarkGfm]} disallowedElements={['script', 'iframe', 'object', 'embed', 'form']} components={mdComponents}>{content}</ReactMarkdown>
          </div>
        )}
      </div>
    );
  }

  // text preview — render as markdown if content looks like it
  const looksLikeMarkdown = /^#{1,3}\s|^\*\*|\|[-:]+\|/m.test(content);

  if (looksLikeMarkdown) {
    return (
      <div>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 6 }}>
          <div style={{ display: 'flex', gap: 4 }}>
            <button
              type="button"
              onClick={() => setRawMode(false)}
              style={{
                fontSize: 12, padding: '3px 10px',
                border: '1px solid #d1d5db', borderRadius: '5px 0 0 5px',
                backgroundColor: !rawMode ? '#1d4ed8' : '#f9fafb',
                color: !rawMode ? '#fff' : '#374151',
                cursor: 'pointer',
              }}
            >
              Rendered
            </button>
            <button
              type="button"
              onClick={() => setRawMode(true)}
              style={{
                fontSize: 12, padding: '3px 10px',
                border: '1px solid #d1d5db', borderRadius: '0 5px 5px 0',
                backgroundColor: rawMode ? '#1d4ed8' : '#f9fafb',
                color: rawMode ? '#fff' : '#374151',
                cursor: 'pointer',
              }}
            >
              Raw
            </button>
          </div>
          <CopyButton text={content} />
        </div>
        {preview.truncated && (
          <p style={{ color: '#d97706', fontSize: 12, marginBottom: 8 }}>Content truncated (file exceeds 1 MB preview limit).</p>
        )}
        {rawMode ? (
          <pre style={{
            margin: 0, padding: 12, backgroundColor: '#f9fafb', borderRadius: 6,
            fontSize: 12, fontFamily: 'monospace', whiteSpace: 'pre-wrap',
            wordBreak: 'break-all', maxHeight: 600, overflow: 'auto',
          }}>
            {content}
          </pre>
        ) : (
          <div style={{
            padding: 12, backgroundColor: '#f9fafb', borderRadius: 6,
            fontSize: 14, lineHeight: 1.6, maxHeight: 600, overflow: 'auto',
          }}>
            <ReactMarkdown remarkPlugins={[remarkGfm]} disallowedElements={['script', 'iframe', 'object', 'embed', 'form']} components={mdComponents}>{content}</ReactMarkdown>
          </div>
        )}
      </div>
    );
  }

  // plain text fallback
  return (
    <div>
      <div style={{ display: 'flex', justifyContent: 'flex-end', marginBottom: 6 }}>
        <CopyButton text={content} />
      </div>
      {preview.truncated && (
        <p style={{ color: '#d97706', fontSize: 12, marginBottom: 8 }}>Content truncated (file exceeds 1 MB preview limit).</p>
      )}
      <pre style={{
        margin: 0, padding: 12, backgroundColor: '#f9fafb', borderRadius: 6,
        fontSize: 12, fontFamily: 'monospace', whiteSpace: 'pre-wrap',
        wordBreak: 'break-all', maxHeight: 600, overflow: 'auto',
      }}>
        {content}
      </pre>
    </div>
  );
}
