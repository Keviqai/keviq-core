'use client';

import Link from 'next/link';
import { useParams, useSearchParams } from 'next/navigation';
import { Suspense } from 'react';
import { useApprovalList, useMembers } from '@keviq/server-state';
import { approvalDetailPath, approvalsPath } from '@keviq/routing';
import { StatusBadge } from '@/modules/shared/status-badge';
import { errorBoxStyle, errorTitleStyle, errorBodyStyle } from '@/modules/shared/ui-styles';
import { resolveDisplayName } from '@/modules/approval/member-display';

const DECISION_FILTERS = [
  { label: 'All', value: undefined },
  { label: 'Pending', value: 'pending' },
  { label: 'Approved', value: 'approved' },
  { label: 'Rejected', value: 'rejected' },
] as const;

function ApprovalsListContent() {
  const params = useParams<{ workspaceId: string }>();
  const searchParams = useSearchParams();
  const workspaceId = params.workspaceId;
  const decisionFilter = searchParams.get('decision') ?? undefined;
  const assignedToMe = searchParams.get('reviewer_id') === 'me';

  const { data, isLoading, isError, error } = useApprovalList(
    workspaceId,
    decisionFilter,
    assignedToMe ? 'me' : undefined,
  );
  const approvals = data?.items ?? [];
  const { data: members } = useMembers(workspaceId);

  return (
    <div>
      <h1 style={{ fontSize: 24, fontWeight: 700, marginBottom: 4 }}>Approval History</h1>
      <p style={{ fontSize: 13, color: '#6b7280', marginBottom: 16, margin: '0 0 16px' }}>Past approval decisions. For items needing your action now, check <Link href={`/workspaces/${workspaceId}/review`} style={{ color: '#1d4ed8', textDecoration: 'none' }}>Needs Review</Link>.</p>

      {/* Filter tabs */}
      <div style={{ display: 'flex', gap: 8, marginBottom: 16, flexWrap: 'wrap' }}>
        {DECISION_FILTERS.map((f) => {
          const isActive = !assignedToMe && decisionFilter === f.value;
          const href = f.value
            ? approvalsPath(workspaceId) + `?decision=${f.value}`
            : approvalsPath(workspaceId);
          return (
            <Link
              key={f.label}
              href={href}
              style={{
                padding: '6px 14px',
                borderRadius: 6,
                fontSize: 13,
                textDecoration: 'none',
                backgroundColor: isActive ? '#1d4ed8' : '#f3f4f6',
                color: isActive ? '#fff' : '#374151',
                fontWeight: isActive ? 600 : 400,
              }}
            >
              {f.label}
            </Link>
          );
        })}
        <Link
          href={approvalsPath(workspaceId) + '?reviewer_id=me'}
          style={{
            padding: '6px 14px',
            borderRadius: 6,
            fontSize: 13,
            textDecoration: 'none',
            backgroundColor: assignedToMe ? '#1d4ed8' : '#f3f4f6',
            color: assignedToMe ? '#fff' : '#374151',
            fontWeight: assignedToMe ? 600 : 400,
          }}
        >
          Assigned to me
        </Link>
      </div>

      {isLoading ? (
        <p style={{ color: '#6b7280' }}>Loading approvals...</p>
      ) : isError ? (
        <div style={errorBoxStyle} role="alert">
          <p style={errorTitleStyle}>Failed to load approvals</p>
          <p style={errorBodyStyle}>{error instanceof Error ? error.message : 'An unexpected error occurred.'}</p>
        </div>
      ) : approvals.length === 0 ? (
        <div style={{ padding: 32, textAlign: 'center', border: '1px solid #e5e7eb', borderRadius: 8 }}>
          <p style={{ fontSize: 14, color: '#9ca3af', marginBottom: 8 }}>
            {assignedToMe
              ? 'No approvals assigned to you.'
              : `No approvals${decisionFilter ? ` with status "${decisionFilter}"` : ''}.`}
          </p>
          <p style={{ fontSize: 13, color: '#9ca3af' }}>
            {assignedToMe
              ? 'Approvals assigned to you will appear here.'
              : 'Approvals appear when a task run requires human review.'}
          </p>
        </div>
      ) : (
        <table style={{ width: '100%', borderCollapse: 'collapse' }}>
          <thead>
            <tr style={{ borderBottom: '2px solid #e5e7eb' }}>
              <th style={{ textAlign: 'left', padding: '8px 0', fontSize: 13, color: '#6b7280' }}>Prompt</th>
              <th style={{ textAlign: 'left', padding: '8px 0', fontSize: 13, color: '#6b7280' }}>Target</th>
              <th style={{ textAlign: 'left', padding: '8px 0', fontSize: 13, color: '#6b7280' }}>Reviewer</th>
              <th style={{ textAlign: 'left', padding: '8px 0', fontSize: 13, color: '#6b7280' }}>Decision</th>
              <th style={{ textAlign: 'right', padding: '8px 0', fontSize: 13, color: '#6b7280' }}>Requested</th>
            </tr>
          </thead>
          <tbody>
            {approvals.map((a) => (
              <tr key={a.approval_id} style={{ borderBottom: '1px solid #f3f4f6' }}>
                <td style={{ padding: '8px 0' }}>
                  <Link
                    href={approvalDetailPath(workspaceId, a.approval_id)}
                    style={{ color: '#1d4ed8', textDecoration: 'none', fontSize: 14 }}
                  >
                    {a.prompt
                      ? a.prompt.length > 60 ? a.prompt.slice(0, 60) + '...' : a.prompt
                      : 'Approval required'}
                  </Link>
                </td>
                <td style={{ padding: '8px 0', fontSize: 13, color: '#6b7280' }}>
                  {a.target_type === 'tool_call' && a.tool_context
                    ? `Tool: ${a.tool_context.tool_name}`
                    : (a.artifact_name ?? a.target_type)}
                </td>
                <td style={{ padding: '8px 0', fontSize: 13, color: '#6b7280' }}>
                  {a.reviewer_id ? (
                    <span style={{
                      display: 'inline-block', padding: '2px 8px',
                      backgroundColor: '#eff6ff', color: '#1d4ed8',
                      borderRadius: 4, fontSize: 12, fontWeight: 500,
                    }}>
                      {resolveDisplayName(a.reviewer_id, members)}
                    </span>
                  ) : '—'}
                </td>
                <td style={{ padding: '8px 0' }}>
                  <StatusBadge status={a.decision} />
                </td>
                <td style={{ padding: '8px 0', textAlign: 'right', fontSize: 13, color: '#6b7280' }}>
                  {new Date(a.created_at).toLocaleDateString()}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
    </div>
  );
}

export default function ApprovalsPage() {
  return (
    <Suspense fallback={<p style={{ color: '#6b7280' }}>Loading...</p>}>
      <ApprovalsListContent />
    </Suspense>
  );
}
