'use client';

import { useState } from 'react';
import { useInviteMember } from '@keviq/server-state';
import { ApiClientError } from '@keviq/api-client';

const ASSIGNABLE_ROLES = ['viewer', 'editor', 'admin'] as const;

export function InviteForm({ workspaceId }: { workspaceId: string }) {
  const [userId, setUserId] = useState('');
  const [role, setRole] = useState<string>('viewer');
  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState(false);
  const invite = useInviteMember(workspaceId);

  function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    if (invite.isPending) return;
    setError(null);
    setSuccess(false);

    const trimmed = userId.trim();
    if (!trimmed) {
      setError('User ID is required.');
      return;
    }

    invite.mutate(
      { user_id: trimmed, role },
      {
        onSuccess: () => {
          setUserId('');
          setRole('viewer');
          setSuccess(true);
          setTimeout(() => setSuccess(false), 3000);
        },
        onError: (err) => {
          if (err instanceof ApiClientError) {
            if (err.status === 409) {
              setError('This user is already a member of this workspace.');
            } else if (err.status === 403) {
              setError('You do not have permission to invite members.');
            } else if (err.status === 400) {
              setError('Invalid user ID or role.');
            } else {
              setError('Failed to invite member.');
            }
          } else {
            setError('Failed to invite member.');
          }
        },
      },
    );
  }

  return (
    <div style={{
      marginBottom: 24,
      padding: 16,
      border: '1px solid #e5e7eb',
      borderRadius: 8,
      backgroundColor: '#f9fafb',
    }}>
      <h3 style={{ fontSize: 14, fontWeight: 600, margin: 0, marginBottom: 12, color: '#374151' }}>
        Invite Member
      </h3>
      <form onSubmit={handleSubmit} style={{ display: 'flex', gap: 8, alignItems: 'flex-end', flexWrap: 'wrap' }}>
        <div style={{ flex: 1, minWidth: 200 }}>
          <label style={{ display: 'block', fontSize: 12, color: '#6b7280', marginBottom: 4 }}>User ID</label>
          <input
            type="text"
            value={userId}
            onChange={(e) => setUserId(e.target.value)}
            placeholder="Enter user UUID..."
            style={{
              width: '100%',
              padding: '8px 12px',
              border: '1px solid #d1d5db',
              borderRadius: 6,
              fontSize: 14,
              boxSizing: 'border-box',
            }}
          />
        </div>
        <div style={{ minWidth: 120 }}>
          <label style={{ display: 'block', fontSize: 12, color: '#6b7280', marginBottom: 4 }}>Role</label>
          <select
            value={role}
            onChange={(e) => setRole(e.target.value)}
            style={{
              width: '100%',
              padding: '8px 12px',
              border: '1px solid #d1d5db',
              borderRadius: 6,
              fontSize: 14,
              backgroundColor: 'white',
            }}
          >
            {ASSIGNABLE_ROLES.map((r) => (
              <option key={r} value={r}>{r}</option>
            ))}
          </select>
        </div>
        <button
          type="submit"
          disabled={invite.isPending}
          style={{
            padding: '8px 20px',
            backgroundColor: '#1d4ed8',
            color: 'white',
            border: 'none',
            borderRadius: 6,
            fontSize: 14,
            fontWeight: 600,
            cursor: invite.isPending ? 'not-allowed' : 'pointer',
            opacity: invite.isPending ? 0.7 : 1,
          }}
        >
          {invite.isPending ? 'Inviting...' : 'Invite'}
        </button>
      </form>
      {error && (
        <p style={{ margin: 0, marginTop: 8, fontSize: 13, color: '#991b1b' }}>{error}</p>
      )}
      {success && (
        <p style={{ margin: 0, marginTop: 8, fontSize: 13, color: '#065f46' }}>Member invited successfully.</p>
      )}
    </div>
  );
}
