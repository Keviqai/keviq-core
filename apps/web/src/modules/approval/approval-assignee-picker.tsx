'use client';

import { useMembers } from '@keviq/server-state';

interface ApprovalAssigneePickerProps {
  workspaceId: string;
  value: string | null;
  onChange: (reviewerId: string | null) => void;
  disabled?: boolean;
}

export function ApprovalAssigneePicker({
  workspaceId,
  value,
  onChange,
  disabled,
}: ApprovalAssigneePickerProps) {
  const { data: members, isLoading } = useMembers(workspaceId);

  return (
    <div>
      <label
        htmlFor="approval-reviewer"
        style={{ fontSize: 13, fontWeight: 500, display: 'block', marginBottom: 6 }}
      >
        Assign reviewer <span style={{ color: '#9ca3af', fontWeight: 400 }}>(optional)</span>
      </label>
      <select
        id="approval-reviewer"
        value={value ?? ''}
        onChange={(e) => onChange(e.target.value || null)}
        disabled={disabled || isLoading}
        style={{
          width: '100%', padding: '7px 10px', fontSize: 13,
          border: '1px solid #d1d5db', borderRadius: 6,
          backgroundColor: '#fff', color: '#374151',
          opacity: disabled || isLoading ? 0.6 : 1,
          cursor: disabled || isLoading ? 'not-allowed' : 'pointer',
        }}
      >
        <option value="">No reviewer assigned</option>
        {(members ?? []).map((m) => (
          <option key={m.user_id} value={m.user_id}>
            {m.display_name || m.email || m.user_id.slice(0, 8) + '…'} ({m.role})
          </option>
        ))}
      </select>
    </div>
  );
}
