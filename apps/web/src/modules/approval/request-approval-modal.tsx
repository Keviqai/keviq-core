'use client';

import { useState } from 'react';
import { useCreateApproval } from '@keviq/server-state';
import { ApprovalAssigneePicker } from './approval-assignee-picker';

interface RequestApprovalModalProps {
  workspaceId: string;
  artifactId: string;
  artifactName: string;
  onClose: () => void;
}

const MAX_PROMPT = 2000;

export function RequestApprovalModal({
  workspaceId,
  artifactId,
  artifactName,
  onClose,
}: RequestApprovalModalProps) {
  const [prompt, setPrompt] = useState('');
  const [reviewerId, setReviewerId] = useState<string | null>(null);
  const { mutate, isPending, isSuccess, isError, error, reset } = useCreateApproval();

  function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    if (isPending || !prompt.trim()) return;
    mutate({ workspaceId, req: { target_id: artifactId, prompt: prompt.trim(), reviewer_id: reviewerId ?? undefined } });
  }

  function handleClose() {
    if (isPending) return;
    reset();
    onClose();
  }

  return (
    <div
      role="dialog"
      aria-modal="true"
      aria-labelledby="approval-modal-title"
      style={{
        position: 'fixed', inset: 0, zIndex: 50,
        display: 'flex', alignItems: 'center', justifyContent: 'center',
        backgroundColor: 'rgba(0,0,0,0.4)',
      }}
      onClick={(e) => { if (e.target === e.currentTarget && !isPending) handleClose(); }}
    >
      <div style={{
        backgroundColor: '#fff', borderRadius: 12, padding: 24,
        width: '100%', maxWidth: 480, boxShadow: '0 20px 60px rgba(0,0,0,0.15)',
      }}>
        <h2 id="approval-modal-title" style={{ fontSize: 18, fontWeight: 700, marginBottom: 4 }}>
          Request Approval
        </h2>
        <p style={{ fontSize: 13, color: '#6b7280', marginBottom: 16 }}>
          for <strong>{artifactName}</strong>
        </p>

        {isSuccess ? (
          <div>
            <div style={{
              padding: '12px 16px', backgroundColor: '#f0fdf4',
              border: '1px solid #bbf7d0', borderRadius: 8, marginBottom: 16,
            }}>
              <p style={{ color: '#166534', fontWeight: 600, margin: 0 }}>Approval request submitted</p>
              <p style={{ color: '#15803d', fontSize: 13, margin: '4px 0 0' }}>
                The workspace will be notified for review.
              </p>
            </div>
            <button
              onClick={handleClose}
              style={{
                width: '100%', padding: '8px 16px', backgroundColor: '#1d4ed8',
                color: '#fff', border: 'none', borderRadius: 6, cursor: 'pointer',
                fontSize: 14, fontWeight: 500,
              }}
            >
              Close
            </button>
          </div>
        ) : (
          <form onSubmit={handleSubmit}>
            <label htmlFor="approval-prompt" style={{ fontSize: 13, fontWeight: 500, display: 'block', marginBottom: 6 }}>
              What needs review? <span style={{ color: '#dc2626' }}>*</span>
            </label>
            <textarea
              id="approval-prompt"
              value={prompt}
              onChange={(e) => setPrompt(e.target.value)}
              maxLength={MAX_PROMPT}
              rows={4}
              placeholder="Describe what you'd like reviewers to check..."
              disabled={isPending}
              style={{
                width: '100%', padding: '8px 12px', fontSize: 13,
                border: '1px solid #d1d5db', borderRadius: 6, resize: 'vertical',
                outline: 'none', fontFamily: 'inherit', boxSizing: 'border-box',
                opacity: isPending ? 0.6 : 1,
              }}
            />
            <div style={{ fontSize: 11, color: '#9ca3af', textAlign: 'right', marginBottom: 8 }}>
              {prompt.length}/{MAX_PROMPT}
            </div>

            <div style={{ marginBottom: 12 }}>
              <ApprovalAssigneePicker
                workspaceId={workspaceId}
                value={reviewerId}
                onChange={setReviewerId}
                disabled={isPending}
              />
            </div>

            {isError && (
              <div style={{
                padding: '8px 12px', backgroundColor: '#fef2f2',
                border: '1px solid #fecaca', borderRadius: 6, marginBottom: 12,
                fontSize: 13, color: '#991b1b',
              }}>
                {error instanceof Error ? error.message : 'Failed to submit approval request.'}
              </div>
            )}

            <div style={{ display: 'flex', gap: 8, justifyContent: 'flex-end' }}>
              <button
                type="button"
                onClick={handleClose}
                disabled={isPending}
                style={{
                  padding: '8px 16px', backgroundColor: '#f3f4f6',
                  color: '#374151', border: 'none', borderRadius: 6,
                  cursor: isPending ? 'not-allowed' : 'pointer', fontSize: 14,
                  opacity: isPending ? 0.6 : 1,
                }}
              >
                Cancel
              </button>
              <button
                type="submit"
                disabled={isPending || !prompt.trim()}
                style={{
                  padding: '8px 16px', backgroundColor: '#1d4ed8',
                  color: '#fff', border: 'none', borderRadius: 6,
                  cursor: isPending || !prompt.trim() ? 'not-allowed' : 'pointer',
                  fontSize: 14, fontWeight: 500,
                  opacity: isPending || !prompt.trim() ? 0.6 : 1,
                }}
              >
                {isPending ? 'Submitting...' : 'Submit Request'}
              </button>
            </div>
          </form>
        )}
      </div>
    </div>
  );
}
