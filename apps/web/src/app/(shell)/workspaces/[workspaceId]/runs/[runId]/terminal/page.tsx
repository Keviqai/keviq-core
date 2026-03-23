'use client';

import { useEffect, useRef, useState } from 'react';
import Link from 'next/link';
import { useParams } from 'next/navigation';
import {
  useTerminalSession,
  useTerminalHistory,
  useCreateTerminalSession,
  useExecCommand,
  useCloseTerminalSession,
  useRun,
} from '@keviq/server-state';
import { useWorkspaceCapabilities } from '@/modules/shared/use-workspace-capabilities';
import { runDetailPath } from '@keviq/routing';
import { TerminalOutput } from './_components/terminal-output';
import { TerminalInput } from './_components/terminal-input';

export default function TerminalPage() {
  const params = useParams<{ workspaceId: string; runId: string }>();
  const workspaceId = params.workspaceId;
  const runId = params.runId;
  const { capabilities, isLoading: capsLoading } = useWorkspaceCapabilities(workspaceId);
  const canTerminal = capabilities.includes('run:terminal');

  const [sessionId, setSessionId] = useState<string | null>(null);
  const createSession = useCreateTerminalSession();
  const closeSession = useCloseTerminalSession();
  const { data: sessionData } = useTerminalSession(sessionId);
  const { data: historyData } = useTerminalHistory(sessionId);
  const execCommand = useExecCommand(sessionId ?? '');
  const { data: runData } = useRun(runId);
  const initRef = useRef(false);

  // Create session on mount if run has a sandbox
  useEffect(() => {
    if (initRef.current || !workspaceId || !runId || !canTerminal) return;
    if (!runData) return;

    const sandboxId = runData.sandbox_id;
    if (!sandboxId) return;

    initRef.current = true;
    createSession.mutate(
      { sandbox_id: sandboxId, run_id: runId, workspace_id: workspaceId },
      {
        onSuccess: (session) => {
          setSessionId(session.id);
        },
      },
    );
  // eslint-disable-next-line react-hooks/exhaustive-deps -- createSession.mutate is stable
  }, [workspaceId, runId, canTerminal, runData]);

  if (!workspaceId || !runId) return null;

  if (capsLoading) {
    return <p style={{ color: '#6b7280' }}>Loading...</p>;
  }

  if (!canTerminal) {
    return (
      <div style={{ padding: 16 }}>
        <Link
          href={runDetailPath(workspaceId, runId)}
          style={{ color: '#6b7280', fontSize: 13, textDecoration: 'none' }}
        >
          &larr; Back to run
        </Link>
        <div style={{ marginTop: 16, padding: 16, backgroundColor: '#fef2f2', borderRadius: 8, border: '1px solid #fecaca' }}>
          <p style={{ color: '#991b1b', fontWeight: 600, marginBottom: 4 }}>Access denied</p>
          <p style={{ color: '#b91c1c', fontSize: 13 }}>
            You do not have permission to use the terminal for this run.
          </p>
        </div>
      </div>
    );
  }

  const isClosed = sessionData?.status === 'closed';
  const commands = historyData?.items ?? [];

  function handleExec(command: string) {
    if (!sessionId || isClosed) return;
    execCommand.mutate({ command });
  }

  function handleClose() {
    if (!sessionId) return;
    closeSession.mutate(sessionId);
  }

  return (
    <div style={{ display: 'flex', flexDirection: 'column', height: '100%' }}>
      {/* Header */}
      <div style={{ padding: '8px 16px', borderBottom: '1px solid #374151', backgroundColor: '#111827', display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
          <Link
            href={runDetailPath(workspaceId, runId)}
            style={{ color: '#9ca3af', fontSize: 13, textDecoration: 'none' }}
          >
            &larr; Run
          </Link>
          <span style={{ color: '#e5e7eb', fontWeight: 600, fontSize: 14 }}>Terminal</span>
          {sessionId && (
            <span style={{
              fontSize: 11,
              padding: '1px 6px',
              borderRadius: 4,
              backgroundColor: isClosed ? '#374151' : '#065f46',
              color: isClosed ? '#9ca3af' : '#6ee7b7',
            }}>
              {isClosed ? 'closed' : 'active'}
            </span>
          )}
        </div>
        {sessionId && !isClosed && (
          <button
            onClick={handleClose}
            disabled={closeSession.isPending}
            style={{
              padding: '3px 10px',
              backgroundColor: '#374151',
              color: '#d1d5db',
              border: '1px solid #4b5563',
              borderRadius: 4,
              fontSize: 12,
              cursor: closeSession.isPending ? 'not-allowed' : 'pointer',
            }}
          >
            Close Session
          </button>
        )}
      </div>

      {/* Output area */}
      <div style={{ flex: 1, overflow: 'auto', backgroundColor: '#0f172a' }}>
        {createSession.isPending ? (
          <p style={{ color: '#6b7280', padding: 16, fontFamily: 'monospace', fontSize: 13 }}>
            Creating terminal session...
          </p>
        ) : createSession.isError ? (
          <p style={{ color: '#f87171', padding: 16, fontFamily: 'monospace', fontSize: 13 }}>
            Failed to create session: {createSession.error instanceof Error ? createSession.error.message : 'Unknown error'}
          </p>
        ) : (
          <TerminalOutput commands={commands} isExecuting={execCommand.isPending} />
        )}
      </div>

      {/* Input area */}
      {sessionId && !isClosed && (
        <TerminalInput
          onSubmit={handleExec}
          disabled={execCommand.isPending || isClosed}
        />
      )}
    </div>
  );
}
