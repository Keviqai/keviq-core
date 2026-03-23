'use client';

import { useState } from 'react';
import type { ArtifactAnnotation, WorkspaceMember } from '@keviq/domain-types';
import { useArtifactAnnotations, useCreateAnnotation, useMembers } from '@keviq/server-state';
import { resolveDisplayName } from '@/modules/approval/member-display';

const MAX_BODY = 4000;

function formatRelativeTime(isoString: string): string {
  const diff = Date.now() - new Date(isoString).getTime();
  const mins = Math.floor(diff / 60_000);
  if (mins < 1) return 'just now';
  if (mins < 60) return `${mins}m ago`;
  const hrs = Math.floor(mins / 60);
  if (hrs < 24) return `${hrs}h ago`;
  const days = Math.floor(hrs / 24);
  return `${days}d ago`;
}

function AnnotationItem({ annotation, members }: { annotation: ArtifactAnnotation; members: WorkspaceMember[] | undefined }) {
  return (
    <div style={{
      padding: '10px 12px',
      borderBottom: '1px solid #f3f4f6',
      fontSize: 13,
    }}>
      <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 4 }}>
        <span style={{
          fontSize: 11, padding: '2px 6px',
          backgroundColor: '#f3f4f6', color: '#374151',
          borderRadius: 4,
        }}>
          {resolveDisplayName(annotation.author_id, members)}
        </span>
        <span style={{ fontSize: 11, color: '#9ca3af' }}>
          {formatRelativeTime(annotation.created_at)}
        </span>
        <span style={{ fontSize: 11, color: '#d1d5db' }}>
          {new Date(annotation.created_at).toLocaleDateString()}
        </span>
      </div>
      <p style={{ margin: 0, color: '#374151', lineHeight: 1.5, whiteSpace: 'pre-wrap' }}>
        {annotation.body}
      </p>
    </div>
  );
}

export function AnnotationPanel({
  workspaceId,
  artifactId,
}: {
  workspaceId: string;
  artifactId: string;
}) {
  const [draft, setDraft] = useState('');
  const [submitError, setSubmitError] = useState<string | null>(null);

  const { data, isLoading, isError } = useArtifactAnnotations(workspaceId, artifactId);
  const { mutate: createAnnotation, isPending } = useCreateAnnotation(workspaceId, artifactId);
  const { data: members } = useMembers(workspaceId);

  const remaining = MAX_BODY - draft.length;
  const canSubmit = draft.trim().length > 0 && remaining >= 0 && !isPending;

  function handleSubmit() {
    if (!canSubmit) return;
    setSubmitError(null);
    createAnnotation(
      { body: draft.trim() },
      {
        onSuccess: () => setDraft(''),
        onError: (err) => setSubmitError(err.message ?? 'Failed to post annotation'),
      },
    );
  }

  return (
    <div>
      {/* Comment list */}
      {isLoading && (
        <p style={{ color: '#9ca3af', fontSize: 13, marginBottom: 12 }}>Loading annotations...</p>
      )}
      {isError && (
        <p style={{ color: '#b91c1c', fontSize: 13, marginBottom: 12 }}>Failed to load annotations.</p>
      )}
      {data && data.items.length === 0 && (
        <p style={{ color: '#9ca3af', fontSize: 13, marginBottom: 12 }}>No annotations yet.</p>
      )}
      {data && data.items.length > 0 && (
        <div style={{
          border: '1px solid #e5e7eb', borderRadius: 6,
          marginBottom: 16, overflow: 'hidden',
        }}>
          {data.items.map((a) => (
            <AnnotationItem key={a.id} annotation={a} members={members} />
          ))}
        </div>
      )}

      {/* Input */}
      <div>
        <textarea
          value={draft}
          onChange={(e) => setDraft(e.target.value)}
          placeholder="Leave a comment..."
          rows={3}
          style={{
            width: '100%', boxSizing: 'border-box',
            padding: '8px 10px', fontSize: 13,
            border: '1px solid #d1d5db', borderRadius: 6,
            resize: 'vertical', fontFamily: 'inherit',
            outline: 'none',
          }}
        />
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginTop: 6 }}>
          <span style={{
            fontSize: 11,
            color: remaining < 0 ? '#b91c1c' : remaining < 100 ? '#d97706' : '#9ca3af',
          }}>
            {remaining} characters remaining
          </span>
          <button
            type="button"
            onClick={handleSubmit}
            disabled={!canSubmit}
            style={{
              padding: '6px 16px',
              backgroundColor: canSubmit ? '#1d4ed8' : '#e5e7eb',
              color: canSubmit ? '#fff' : '#9ca3af',
              border: 'none', borderRadius: 6,
              fontSize: 13, fontWeight: 500,
              cursor: canSubmit ? 'pointer' : 'not-allowed',
            }}
          >
            {isPending ? 'Posting...' : 'Post'}
          </button>
        </div>
        {submitError && (
          <p style={{ color: '#b91c1c', fontSize: 12, marginTop: 4 }}>{submitError}</p>
        )}
      </div>
    </div>
  );
}
