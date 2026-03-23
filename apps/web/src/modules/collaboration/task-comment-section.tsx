'use client';

import { useState } from 'react';
import type { WorkspaceMember } from '@keviq/domain-types';
import { useTaskComments, useCreateTaskComment } from '@keviq/server-state';
import { resolveDisplayName } from '@/modules/approval/member-display';

/**
 * Task comment section — inline discussion thread on task detail.
 * P6-S2: Allows team members to discuss agent outputs and task progress.
 */

const MAX_BODY = 2000;

interface TaskCommentSectionProps {
  workspaceId: string;
  taskId: string;
  members: WorkspaceMember[] | undefined;
}

function formatRelativeTime(iso: string): string {
  const diff = Date.now() - new Date(iso).getTime();
  const mins = Math.floor(diff / 60_000);
  if (mins < 1) return 'just now';
  if (mins < 60) return `${mins}m ago`;
  const hrs = Math.floor(mins / 60);
  if (hrs < 24) return `${hrs}h ago`;
  return `${Math.floor(hrs / 24)}d ago`;
}

export function TaskCommentSection({ workspaceId, taskId, members }: TaskCommentSectionProps) {
  const [draft, setDraft] = useState('');
  const [submitError, setSubmitError] = useState<string | null>(null);

  const { data, isLoading, isError } = useTaskComments(workspaceId, taskId);
  const { mutate: createComment, isPending } = useCreateTaskComment(workspaceId, taskId);

  const remaining = MAX_BODY - draft.length;
  const canSubmit = draft.trim().length > 0 && remaining >= 0 && !isPending;

  function handleSubmit() {
    if (!canSubmit) return;
    setSubmitError(null);
    createComment(draft.trim(), {
      onSuccess: () => setDraft(''),
      onError: (err) => setSubmitError(err.message ?? 'Failed to post comment'),
    });
  }

  const comments = data?.items ?? [];

  return (
    <div style={{ border: '1px solid #e5e7eb', borderRadius: 8, padding: 16, marginBottom: 20 }}>
      <h3 style={{ fontSize: 14, fontWeight: 600, color: '#374151', marginTop: 0, marginBottom: 12 }}>
        Comments {comments.length > 0 && <span style={{ color: '#9ca3af', fontWeight: 400 }}>({comments.length})</span>}
      </h3>

      {/* Comment list */}
      {isLoading && <p style={{ color: '#9ca3af', fontSize: 13 }}>Loading comments...</p>}
      {isError && <p style={{ color: '#b91c1c', fontSize: 13 }}>Failed to load comments.</p>}

      {!isLoading && comments.length === 0 && (
        <p style={{ color: '#9ca3af', fontSize: 13, fontStyle: 'italic', marginBottom: 12 }}>
          No comments yet. Start a discussion.
        </p>
      )}

      {comments.length > 0 && (
        <div style={{ marginBottom: 12 }}>
          {comments.map((c) => (
            <div key={c.id} style={{ padding: '8px 0', borderBottom: '1px solid #f3f4f6', fontSize: 13 }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 4 }}>
                <span style={{
                  fontSize: 12, fontWeight: 500, color: '#1d4ed8',
                }}>
                  {resolveDisplayName(c.author_id, members)}
                </span>
                <span style={{ fontSize: 11, color: '#9ca3af' }}>
                  {formatRelativeTime(c.created_at)}
                </span>
              </div>
              <p style={{ margin: 0, color: '#374151', lineHeight: 1.5, whiteSpace: 'pre-wrap' }}>
                {c.body}
              </p>
            </div>
          ))}
        </div>
      )}

      {/* Composer */}
      <textarea
        value={draft}
        onChange={(e) => setDraft(e.target.value)}
        placeholder="Write a comment..."
        rows={2}
        style={{
          width: '100%', boxSizing: 'border-box',
          padding: '8px 10px', fontSize: 13,
          border: '1px solid #d1d5db', borderRadius: 6,
          resize: 'vertical', fontFamily: 'inherit',
        }}
      />
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginTop: 6 }}>
        <span style={{
          fontSize: 11,
          color: remaining < 0 ? '#b91c1c' : remaining < 100 ? '#d97706' : '#9ca3af',
        }}>
          {remaining} chars
        </span>
        <button
          type="button"
          onClick={handleSubmit}
          disabled={!canSubmit}
          style={{
            padding: '6px 14px',
            backgroundColor: canSubmit ? '#1d4ed8' : '#e5e7eb',
            color: canSubmit ? '#fff' : '#9ca3af',
            border: 'none', borderRadius: 6,
            fontSize: 13, fontWeight: 500,
            cursor: canSubmit ? 'pointer' : 'not-allowed',
          }}
        >
          {isPending ? 'Posting...' : 'Comment'}
        </button>
      </div>
      {submitError && <p style={{ color: '#b91c1c', fontSize: 12, marginTop: 4 }}>{submitError}</p>}
    </div>
  );
}
