'use client';

import { useState } from 'react';
import { useCancelTask, useRetryTask } from '@keviq/server-state';

interface TaskActionsProps {
  taskId: string;
  workspaceId: string;
  canCancel: boolean;
  canRetry: boolean;
}

export function TaskActions({ taskId, workspaceId, canCancel, canRetry }: TaskActionsProps) {
  const [confirmCancel, setConfirmCancel] = useState(false);
  const [confirmRetry, setConfirmRetry] = useState(false);
  const cancelMutation = useCancelTask(workspaceId);
  const retryMutation = useRetryTask(workspaceId);

  function handleCancel() {
    cancelMutation.mutate(taskId, { onSuccess: () => setConfirmCancel(false) });
  }

  function handleRetry() {
    retryMutation.mutate(taskId, { onSuccess: () => setConfirmRetry(false) });
  }

  if (!canCancel && !canRetry) return null;

  return (
    <div style={{ display: 'flex', gap: 8 }}>
      {canCancel && !confirmCancel && (
        <button
          onClick={() => setConfirmCancel(true)}
          style={{
            padding: '6px 16px',
            backgroundColor: '#fef2f2',
            color: '#991b1b',
            border: '1px solid #fecaca',
            borderRadius: 6,
            cursor: 'pointer',
            fontSize: 13,
          }}
        >
          Cancel Task
        </button>
      )}

      {confirmCancel && (
        <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
          <span style={{ fontSize: 13, color: '#374151' }}>Cancel this task?</span>
          <button
            onClick={handleCancel}
            disabled={cancelMutation.isPending}
            style={{
              padding: '4px 12px',
              backgroundColor: '#dc2626',
              color: '#fff',
              border: 'none',
              borderRadius: 6,
              cursor: cancelMutation.isPending ? 'not-allowed' : 'pointer',
              fontSize: 13,
              fontWeight: 600,
            }}
          >
            {cancelMutation.isPending ? 'Cancelling...' : 'Confirm'}
          </button>
          <button
            onClick={() => setConfirmCancel(false)}
            disabled={cancelMutation.isPending}
            style={{
              padding: '4px 12px',
              backgroundColor: 'transparent',
              color: '#6b7280',
              border: '1px solid #d1d5db',
              borderRadius: 6,
              cursor: 'pointer',
              fontSize: 13,
            }}
          >
            No
          </button>
          {cancelMutation.isError && (
            <span style={{ fontSize: 12, color: '#991b1b' }}>
              {cancelMutation.error?.message ?? 'Cancel failed'}
            </span>
          )}
        </div>
      )}

      {canRetry && !confirmRetry && (
        <button
          onClick={() => setConfirmRetry(true)}
          style={{
            padding: '6px 16px',
            backgroundColor: '#eff6ff',
            color: '#1d4ed8',
            border: '1px solid #bfdbfe',
            borderRadius: 6,
            cursor: 'pointer',
            fontSize: 13,
          }}
        >
          Retry Task
        </button>
      )}

      {confirmRetry && (
        <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
          <span style={{ fontSize: 13, color: '#374151' }}>Retry this task?</span>
          <button
            onClick={handleRetry}
            disabled={retryMutation.isPending}
            style={{
              padding: '4px 12px',
              backgroundColor: '#2563eb',
              color: '#fff',
              border: 'none',
              borderRadius: 6,
              cursor: retryMutation.isPending ? 'not-allowed' : 'pointer',
              fontSize: 13,
              fontWeight: 600,
            }}
          >
            {retryMutation.isPending ? 'Retrying...' : 'Confirm'}
          </button>
          <button
            onClick={() => setConfirmRetry(false)}
            disabled={retryMutation.isPending}
            style={{
              padding: '4px 12px',
              backgroundColor: 'transparent',
              color: '#6b7280',
              border: '1px solid #d1d5db',
              borderRadius: 6,
              cursor: 'pointer',
              fontSize: 13,
            }}
          >
            No
          </button>
          {retryMutation.isError && (
            <span style={{ fontSize: 12, color: '#991b1b' }}>
              {retryMutation.error?.message ?? 'Retry failed'}
            </span>
          )}
        </div>
      )}
    </div>
  );
}
