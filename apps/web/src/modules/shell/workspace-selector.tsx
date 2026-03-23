'use client';

import { useParams, useRouter } from 'next/navigation';
import { useWorkspaces } from '@keviq/server-state';
import { workspacePath } from '@keviq/routing';

export function WorkspaceSelector() {
  const params = useParams<{ workspaceId: string }>();
  const router = useRouter();
  const { data: workspaces, isLoading } = useWorkspaces();

  const wsList = workspaces ?? [];
  const currentId = params.workspaceId;

  if (isLoading) {
    return <span style={{ fontSize: 14, color: '#d1d5db' }}>Loading...</span>;
  }

  if (wsList.length === 0) {
    return <span style={{ fontSize: 14, color: '#9ca3af' }}>No workspaces</span>;
  }

  return (
    <select
      value={currentId ?? ''}
      onChange={(e) => {
        if (e.target.value) {
          router.push(workspacePath(e.target.value));
        }
      }}
      style={{ fontSize: 14, padding: '4px 8px', border: '1px solid #d1d5db', borderRadius: 4 }}
    >
      {wsList.map((ws) => (
        <option key={ws.id} value={ws.id}>
          {ws.display_name}
        </option>
      ))}
    </select>
  );
}
