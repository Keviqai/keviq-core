'use client';

import { useEffect, useRef } from 'react';
import type { CommandResult } from '@keviq/domain-types';

interface TerminalOutputProps {
  commands: CommandResult[];
  isExecuting: boolean;
}

const STATUS_COLORS: Record<string, string> = {
  completed: '#6ee7b7',
  failed: '#f87171',
  timed_out: '#fbbf24',
  running: '#60a5fa',
};

export function TerminalOutput({ commands, isExecuting }: TerminalOutputProps) {
  const bottomRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [commands.length, isExecuting]);

  return (
    <div style={{ padding: 16, fontFamily: 'monospace', fontSize: 13, lineHeight: 1.6 }}>
      {commands.length === 0 && !isExecuting && (
        <p style={{ color: '#6b7280' }}>Type a command below to get started.</p>
      )}

      {commands.map((cmd) => (
        <div key={cmd.id} style={{ marginBottom: 12 }}>
          {/* Prompt + command */}
          <div style={{ color: '#6ee7b7' }}>
            <span style={{ color: '#9ca3af' }}>$ </span>
            {cmd.command}
          </div>

          {/* stdout */}
          {cmd.stdout && (
            <pre style={{ margin: 0, whiteSpace: 'pre-wrap', wordBreak: 'break-all', color: '#e2e8f0' }}>
              {cmd.stdout}
            </pre>
          )}

          {/* stderr */}
          {cmd.stderr && (
            <pre style={{ margin: 0, whiteSpace: 'pre-wrap', wordBreak: 'break-all', color: '#f87171' }}>
              {cmd.stderr}
            </pre>
          )}

          {/* Exit code badge */}
          {cmd.status !== 'running' && (
            <span style={{
              display: 'inline-block',
              marginTop: 2,
              fontSize: 11,
              padding: '0 4px',
              borderRadius: 3,
              backgroundColor: '#1e293b',
              color: STATUS_COLORS[cmd.status] ?? '#9ca3af',
            }}>
              {cmd.status === 'completed' && cmd.exit_code === 0
                ? 'exit 0'
                : cmd.status === 'timed_out'
                  ? 'timed out'
                  : cmd.exit_code != null
                    ? `exit ${cmd.exit_code}`
                    : cmd.status}
            </span>
          )}
        </div>
      ))}

      {isExecuting && (
        <div style={{ color: '#60a5fa' }}>
          <span style={{ animation: 'pulse 1.5s infinite' }}>Executing...</span>
        </div>
      )}

      <div ref={bottomRef} />
    </div>
  );
}
