'use client';

import { useState } from 'react';
import Link from 'next/link';
import { useParams, useRouter } from 'next/navigation';
import { useApproval, useDecideApproval, useMembers } from '@keviq/server-state';
import { approvalsPath, taskDetailPath, runDetailPath } from '@keviq/routing';
import { StatusBadge } from '@/modules/shared/status-badge';
import { errorBoxStyle, errorTitleStyle, errorBodyStyle } from '@/modules/shared/ui-styles';
import { ApprovalArtifactContextCard } from '@/modules/approval/approval-artifact-context-card';
import { ToolApprovalPanel } from '@/modules/approval/tool-approval-panel';
import { resolveDisplayName } from '@/modules/approval/member-display';

export default function ApprovalDetailPage() {
  const params = useParams<{ workspaceId: string; approvalId: string }>();
  const router = useRouter();
  const workspaceId = params.workspaceId;
  const approvalId = params.approvalId;

  const { data: approval, isLoading, isError, error } = useApproval(workspaceId, approvalId);
  const decideMutation = useDecideApproval();
  const { data: members } = useMembers(workspaceId);

  const [comment, setComment] = useState('');
  const [submitting, setSubmitting] = useState(false);

  if (isLoading) {
    return <p style={{ color: '#6b7280' }}>Loading approval...</p>;
  }

  if (isError) {
    return (
      <div style={errorBoxStyle} role="alert">
        <p style={errorTitleStyle}>Failed to load approval</p>
        <p style={errorBodyStyle}>{error instanceof Error ? error.message : 'An unexpected error occurred.'}</p>
      </div>
    );
  }

  if (!approval) {
    return <p style={{ fontSize: 14, color: '#991b1b' }}>Approval not found.</p>;
  }

  const isPending = approval.decision === 'pending';

  const handleDecide = async (decision: 'approve' | 'reject' | 'override' | 'cancel', decisionComment?: string, overrideOutput?: string) => {
    setSubmitting(true);
    try {
      await decideMutation.mutateAsync({
        workspaceId,
        approvalId,
        req: {
          decision,
          comment: decisionComment || comment || undefined,
          ...(overrideOutput ? { override_output: overrideOutput } : {}),
        },
      });
      router.push(approvalsPath(workspaceId));
    } catch {
      // Error state handled by decideMutation.isError
    } finally {
      setSubmitting(false);
    }
  };

  const isToolCall = approval?.target_type === 'tool_call';

  const targetLink = approval.target_type === 'task'
    ? taskDetailPath(workspaceId, approval.target_id)
    : approval.target_type === 'run'
      ? runDetailPath(workspaceId, approval.target_id)
      : approval.target_type === 'tool_call' && approval.tool_context?.task_id
        ? taskDetailPath(workspaceId, approval.tool_context.task_id)
        : null;

  return (
    <div>
      <Link href={approvalsPath(workspaceId)} style={{ fontSize: 13, color: '#1d4ed8', textDecoration: 'none' }}>
        &larr; Back to Approvals
      </Link>

      <h1 style={{ fontSize: 24, fontWeight: 700, marginTop: 12, marginBottom: 16 }}>
        Approval Detail
      </h1>

      {/* Info card */}
      <div style={{ border: '1px solid #e5e7eb', borderRadius: 8, padding: 20, marginBottom: 20 }}>
        <dl style={{ margin: 0, display: 'grid', gridTemplateColumns: '140px 1fr', gap: '8px 16px' }}>
          <dt style={{ fontSize: 13, color: '#6b7280', fontWeight: 500 }}>Decision</dt>
          <dd style={{ margin: 0 }}><StatusBadge status={approval.decision} /></dd>
          <dt style={{ fontSize: 13, color: '#6b7280', fontWeight: 500 }}>Target</dt>
          <dd style={{ margin: 0, fontSize: 14 }}>
            {targetLink ? (
              <Link href={targetLink} style={{ color: '#1d4ed8', textDecoration: 'none' }}>
                {approval.target_type} &rarr;
              </Link>
            ) : (
              <span>{approval.target_type}: {approval.target_id}</span>
            )}
          </dd>
          <dt style={{ fontSize: 13, color: '#6b7280', fontWeight: 500 }}>Requested by</dt>
          <dd style={{ margin: 0, fontSize: 14 }}>{resolveDisplayName(approval.requested_by, members)}</dd>
          {approval.reviewer_id && (
            <>
              <dt style={{ fontSize: 13, color: '#6b7280', fontWeight: 500 }}>Reviewer</dt>
              <dd style={{ margin: 0, fontSize: 14 }}>
                <span style={{
                  display: 'inline-block', padding: '2px 8px',
                  backgroundColor: '#eff6ff', color: '#1d4ed8',
                  borderRadius: 4, fontSize: 12, fontWeight: 500,
                }}>
                  {resolveDisplayName(approval.reviewer_id, members)}
                </span>
              </dd>
            </>
          )}
          <dt style={{ fontSize: 13, color: '#6b7280', fontWeight: 500 }}>Requested at</dt>
          <dd style={{ margin: 0, fontSize: 14 }}>{new Date(approval.created_at).toLocaleString()}</dd>
          {approval.timeout_at && (
            <>
              <dt style={{ fontSize: 13, color: '#6b7280', fontWeight: 500 }}>Timeout</dt>
              <dd style={{ margin: 0, fontSize: 14 }}>{new Date(approval.timeout_at).toLocaleString()}</dd>
            </>
          )}
        </dl>
      </div>

      {/* Artifact context card — only for artifact targets */}
      {approval.target_type === 'artifact' && (
        <ApprovalArtifactContextCard
          workspaceId={workspaceId}
          artifactId={approval.target_id}
          context={approval.artifact_context}
        />
      )}

      {/* Prompt */}
      {approval.prompt && (
        <div style={{ border: '1px solid #e5e7eb', borderRadius: 8, padding: 16, marginBottom: 20 }}>
          <h3 style={{ fontSize: 14, fontWeight: 600, marginBottom: 8, color: '#374151' }}>Prompt</h3>
          <p style={{ fontSize: 14, color: '#374151', whiteSpace: 'pre-wrap', margin: 0 }}>
            {approval.prompt}
          </p>
        </div>
      )}

      {/* Decision result (if already decided) */}
      {!isPending && (
        <div style={{ border: '1px solid #e5e7eb', borderRadius: 8, padding: 16, marginBottom: 20 }}>
          <h3 style={{ fontSize: 14, fontWeight: 600, marginBottom: 8, color: '#374151' }}>Decision</h3>
          <dl style={{ margin: 0, display: 'grid', gridTemplateColumns: '140px 1fr', gap: '8px 16px' }}>
            {approval.decided_by_id && (
              <>
                <dt style={{ fontSize: 13, color: '#6b7280' }}>Decided by</dt>
                <dd style={{ margin: 0, fontSize: 14 }}>{resolveDisplayName(approval.decided_by_id, members)}</dd>
              </>
            )}
            {approval.decided_at && (
              <>
                <dt style={{ fontSize: 13, color: '#6b7280' }}>Decided at</dt>
                <dd style={{ margin: 0, fontSize: 14 }}>{new Date(approval.decided_at).toLocaleString()}</dd>
              </>
            )}
            {approval.decision_comment && (
              <>
                <dt style={{ fontSize: 13, color: '#6b7280' }}>Comment</dt>
                <dd style={{ margin: 0, fontSize: 14 }}>{approval.decision_comment}</dd>
              </>
            )}
          </dl>
        </div>
      )}

      {/* Actions — tool_call targets get the full 4-action panel */}
      {isPending && isToolCall && approval.tool_context && (
        <ToolApprovalPanel
          toolContext={approval.tool_context}
          isPending={isPending}
          onDecide={handleDecide}
          isSubmitting={submitting}
          error={decideMutation.isError ? (decideMutation.error?.message ?? 'Failed to submit decision') : null}
        />
      )}

      {/* Actions — non-tool targets get standard approve/reject */}
      {isPending && !isToolCall && (
        <div style={{ border: '1px solid #e5e7eb', borderRadius: 8, padding: 16 }}>
          <h3 style={{ fontSize: 14, fontWeight: 600, marginBottom: 12, color: '#374151' }}>Take Action</h3>
          <textarea
            value={comment}
            onChange={(e) => setComment(e.target.value)}
            placeholder="Optional comment..."
            rows={3}
            style={{
              width: '100%', padding: 10, fontSize: 14, borderRadius: 6,
              border: '1px solid #d1d5db', marginBottom: 12, resize: 'vertical',
            }}
          />
          <div style={{ display: 'flex', gap: 12 }}>
            <button
              onClick={() => handleDecide('approve')}
              disabled={submitting}
              style={{
                padding: '8px 20px', borderRadius: 6, border: 'none', cursor: 'pointer',
                backgroundColor: '#059669', color: '#fff', fontWeight: 600, fontSize: 14,
                opacity: submitting ? 0.6 : 1,
              }}
            >
              {submitting ? 'Processing...' : 'Approve'}
            </button>
            <button
              onClick={() => handleDecide('reject')}
              disabled={submitting}
              style={{
                padding: '8px 20px', borderRadius: 6, border: 'none', cursor: 'pointer',
                backgroundColor: '#dc2626', color: '#fff', fontWeight: 600, fontSize: 14,
                opacity: submitting ? 0.6 : 1,
              }}
            >
              {submitting ? 'Processing...' : 'Reject'}
            </button>
          </div>
          {decideMutation.isError && (
            <p style={{ color: '#991b1b', fontSize: 13, marginTop: 8 }}>
              Error: {decideMutation.error?.message ?? 'Failed to submit decision'}
            </p>
          )}
        </div>
      )}
    </div>
  );
}
