'use client';

import Link from 'next/link';
import { useParams, useRouter } from 'next/navigation';
import { useMembers, useAuth, useWorkspaces } from '@keviq/server-state';
import { useWorkspaceCapabilities } from '@/modules/shared/use-workspace-capabilities';
import { settingsPath, workspacePath } from '@keviq/routing';
import { ApiClientError } from '@keviq/api-client';
import { InviteForm } from './_components/invite-form';
import { MemberRow } from './_components/member-row';

export default function MembersPage() {
  const params = useParams<{ workspaceId: string }>();
  const workspaceId = params.workspaceId;
  const router = useRouter();
  const { data: authData } = useAuth();
  const currentUserId = authData?.user?.id;
  const { data: members, isLoading, isError, error } = useMembers(workspaceId);
  const { capabilities, isLoading: capsLoading } = useWorkspaceCapabilities(workspaceId);
  const canManageMembers = capabilities.includes('workspace:manage_members');
  const { data: allWorkspaces } = useWorkspaces();

  if (!workspaceId) return null;

  if (isLoading || capsLoading) {
    return <p style={{ color: '#6b7280' }}>Loading members...</p>;
  }

  if (isError) {
    const status = error instanceof ApiClientError ? error.status : 0;
    if (status === 404) {
      return (
        <div style={{ padding: 16, backgroundColor: '#fef2f2', borderRadius: 8, border: '1px solid #fecaca' }}>
          <p style={{ color: '#991b1b', fontWeight: 600, marginBottom: 4 }}>Workspace not found</p>
          <p style={{ color: '#b91c1c', fontSize: 13 }}>
            This workspace does not exist or you are not a member.
          </p>
        </div>
      );
    }
    if (status === 403) {
      return (
        <div style={{ padding: 16, backgroundColor: '#fef2f2', borderRadius: 8, border: '1px solid #fecaca' }}>
          <p style={{ color: '#991b1b', fontWeight: 600, marginBottom: 4 }}>Access denied</p>
          <p style={{ color: '#b91c1c', fontSize: 13 }}>
            You do not have permission to view members of this workspace.
          </p>
          <Link href={workspacePath(workspaceId)} style={{ color: '#1d4ed8', fontSize: 13 }}>
            Back to workspace
          </Link>
        </div>
      );
    }
    return (
      <div style={{ padding: 16, backgroundColor: '#fef2f2', borderRadius: 8, border: '1px solid #fecaca' }}>
        <p style={{ color: '#991b1b', fontWeight: 600, marginBottom: 4 }}>Failed to load members</p>
        <p style={{ color: '#b91c1c', fontSize: 13 }}>
          {error instanceof Error ? error.message : 'An unexpected error occurred.'}
        </p>
        <Link href={settingsPath(workspaceId)} style={{ color: '#1d4ed8', fontSize: 13 }}>
          Back to settings
        </Link>
      </div>
    );
  }

  const memberList = members ?? [];

  return (
    <div>
      <div style={{ marginBottom: 8 }}>
        <Link
          href={settingsPath(workspaceId)}
          style={{ color: '#6b7280', fontSize: 13, textDecoration: 'none' }}
        >
          &larr; Settings
        </Link>
      </div>

      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 24 }}>
        <h1 style={{ fontSize: 24, fontWeight: 700, margin: 0 }}>
          Members
          {memberList.length > 0 && (
            <span style={{ fontWeight: 400, fontSize: 16, color: '#9ca3af', marginLeft: 8 }}>
              ({memberList.length})
            </span>
          )}
        </h1>
      </div>

      {canManageMembers && (
        <InviteForm workspaceId={workspaceId} />
      )}

      {memberList.length === 0 ? (
        <div style={{ padding: 32, textAlign: 'center', border: '1px dashed #d1d5db', borderRadius: 8 }}>
          <p style={{ fontSize: 14, color: '#374151', marginBottom: 4 }}>No members yet</p>
          <p style={{ fontSize: 13, color: '#6b7280', margin: 0 }}>Invite users to collaborate in this workspace.</p>
        </div>
      ) : (
        <div style={{ border: '1px solid #e5e7eb', borderRadius: 8, overflow: 'hidden' }}>
          <table style={{ width: '100%', borderCollapse: 'collapse' }}>
            <thead>
              <tr style={{ borderBottom: '1px solid #e5e7eb', backgroundColor: '#f9fafb' }}>
                <th style={{ padding: '10px 12px', fontSize: 12, color: '#6b7280', textAlign: 'left', fontWeight: 500 }}>User</th>
                <th style={{ padding: '10px 12px', fontSize: 12, color: '#6b7280', textAlign: 'left', fontWeight: 500 }}>Role</th>
                <th style={{ padding: '10px 12px', fontSize: 12, color: '#6b7280', textAlign: 'left', fontWeight: 500 }}>Joined</th>
                <th style={{ padding: '10px 12px', fontSize: 12, color: '#6b7280', textAlign: 'right', fontWeight: 500 }}>Actions</th>
              </tr>
            </thead>
            <tbody>
              {memberList.map((member) => (
                <MemberRow
                  key={member.user_id}
                  workspaceId={workspaceId}
                  member={member}
                  currentUserId={currentUserId}
                  canManageMembers={canManageMembers}
                  onSelfRemoved={() => {
                    const remaining = allWorkspaces?.filter((w) => w.id !== workspaceId);
                    if (remaining && remaining.length > 0) {
                      router.push(workspacePath(remaining[0].id));
                    } else {
                      router.push('/onboarding');
                    }
                  }}
                />
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}
