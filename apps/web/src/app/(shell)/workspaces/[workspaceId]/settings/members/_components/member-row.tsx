'use client';

import { useState } from 'react';
import { useUpdateMemberRole, useRemoveMember } from '@keviq/server-state';
import type { WorkspaceMember } from '@keviq/domain-types';

const ASSIGNABLE_ROLES = ['viewer', 'editor', 'admin'] as const;

interface MemberRowProps {
  workspaceId: string;
  member: WorkspaceMember;
  currentUserId: string | undefined;
  canManageMembers: boolean;
  onSelfRemoved: () => void;
}

export function MemberRow({ workspaceId, member, currentUserId, canManageMembers, onSelfRemoved }: MemberRowProps) {
  const [confirmRemove, setConfirmRemove] = useState(false);
  const updateRole = useUpdateMemberRole(workspaceId);
  const removeMember = useRemoveMember(workspaceId);

  const isSelf = currentUserId === member.user_id;
  const isOwner = member.role === 'owner';
  // Self can leave (unless owner). Admin/owner can remove non-owners.
  const showRemoveAction = isOwner ? false : (isSelf || canManageMembers);

  function handleRoleChange(newRole: string) {
    if (newRole === member.role) return;
    updateRole.mutate({ memberUserId: member.user_id, role: newRole });
  }

  function handleRemove() {
    removeMember.mutate(member.user_id, {
      onSuccess: () => {
        if (isSelf) {
          onSelfRemoved();
        }
        setConfirmRemove(false);
      },
    });
  }

  return (
    <tr style={{ borderBottom: '1px solid #f3f4f6' }}>
      <td style={{ padding: '10px 12px' }}>
        <span style={{ fontSize: 13 }}>
          {member.user_id.slice(0, 8)}...
        </span>
        {isSelf && (
          <span style={{
            marginLeft: 6,
            fontSize: 11,
            color: '#1d4ed8',
            backgroundColor: '#eff6ff',
            padding: '1px 6px',
            borderRadius: 4,
          }}>
            you
          </span>
        )}
      </td>
      <td style={{ padding: '10px 12px' }}>
        {canManageMembers && !isOwner ? (
          <select
            value={member.role}
            onChange={(e) => handleRoleChange(e.target.value)}
            disabled={updateRole.isPending}
            style={{
              padding: '4px 8px',
              border: '1px solid #d1d5db',
              borderRadius: 4,
              fontSize: 13,
              backgroundColor: 'white',
              cursor: updateRole.isPending ? 'not-allowed' : 'pointer',
            }}
          >
            {ASSIGNABLE_ROLES.map((r) => (
              <option key={r} value={r}>{r}</option>
            ))}
          </select>
        ) : (
          <span style={{
            display: 'inline-block',
            padding: '2px 8px',
            borderRadius: 4,
            fontSize: 12,
            fontWeight: 500,
            backgroundColor: isOwner ? '#fef3c7' : '#f3f4f6',
            color: isOwner ? '#92400e' : '#374151',
          }}>
            {member.role}
          </span>
        )}
        {updateRole.isError && (
          <span style={{ marginLeft: 8, fontSize: 12, color: '#991b1b' }}>Failed</span>
        )}
      </td>
      <td style={{ padding: '10px 12px', fontSize: 13, color: '#6b7280' }}>
        {new Date(member.joined_at).toLocaleDateString()}
      </td>
      <td style={{ padding: '10px 12px', textAlign: 'right' }}>
        {showRemoveAction && (
          <>
            {confirmRemove ? (
              <span style={{ display: 'inline-flex', gap: 4, alignItems: 'center' }}>
                <span style={{ fontSize: 12, color: '#991b1b' }}>
                  {isSelf ? 'Leave workspace?' : 'Remove?'}
                </span>
                <button
                  onClick={handleRemove}
                  disabled={removeMember.isPending}
                  style={{
                    padding: '3px 10px',
                    backgroundColor: '#dc2626',
                    color: 'white',
                    border: 'none',
                    borderRadius: 4,
                    fontSize: 12,
                    cursor: removeMember.isPending ? 'not-allowed' : 'pointer',
                  }}
                >
                  {removeMember.isPending ? '...' : 'Yes'}
                </button>
                <button
                  onClick={() => setConfirmRemove(false)}
                  style={{
                    padding: '3px 10px',
                    backgroundColor: 'white',
                    color: '#374151',
                    border: '1px solid #d1d5db',
                    borderRadius: 4,
                    fontSize: 12,
                    cursor: 'pointer',
                  }}
                >
                  No
                </button>
              </span>
            ) : (
              <button
                onClick={() => setConfirmRemove(true)}
                style={{
                  padding: '3px 10px',
                  backgroundColor: 'white',
                  color: '#991b1b',
                  border: '1px solid #fecaca',
                  borderRadius: 4,
                  fontSize: 12,
                  cursor: 'pointer',
                }}
              >
                {isSelf ? 'Leave' : 'Remove'}
              </button>
            )}
          </>
        )}
        {removeMember.isError && (
          <span style={{ marginLeft: 4, fontSize: 12, color: '#991b1b' }}>Failed</span>
        )}
      </td>
    </tr>
  );
}
