'use client';

import { useCallback, useRef, useState } from 'react';

interface TerminalInputProps {
  onSubmit: (command: string) => void;
  disabled: boolean;
}

export function TerminalInput({ onSubmit, disabled }: TerminalInputProps) {
  const [value, setValue] = useState('');
  const [history, setHistory] = useState<string[]>([]);
  const [historyIndex, setHistoryIndex] = useState(-1);
  const inputRef = useRef<HTMLInputElement>(null);

  const handleKeyDown = useCallback(
    (e: React.KeyboardEvent<HTMLInputElement>) => {
      if (e.key === 'Enter' && !e.shiftKey) {
        e.preventDefault();
        const trimmed = value.trim();
        if (!trimmed || disabled) return;
        setHistory((prev) => [trimmed, ...prev].slice(0, 100));
        setHistoryIndex(-1);
        onSubmit(trimmed);
        setValue('');
      }

      if (e.key === 'ArrowUp') {
        e.preventDefault();
        if (history.length === 0) return;
        const next = Math.min(historyIndex + 1, history.length - 1);
        setHistoryIndex(next);
        setValue(history[next]);
      }

      if (e.key === 'ArrowDown') {
        e.preventDefault();
        if (historyIndex <= 0) {
          setHistoryIndex(-1);
          setValue('');
          return;
        }
        const next = historyIndex - 1;
        setHistoryIndex(next);
        setValue(history[next]);
      }
    },
    [value, disabled, onSubmit, history, historyIndex],
  );

  return (
    <div style={{
      padding: '8px 16px',
      backgroundColor: '#1e293b',
      borderTop: '1px solid #374151',
      display: 'flex',
      alignItems: 'center',
      gap: 8,
    }}>
      <span style={{ color: '#6ee7b7', fontFamily: 'monospace', fontSize: 13 }}>$</span>
      <input
        ref={inputRef}
        type="text"
        value={value}
        onChange={(e) => setValue(e.target.value)}
        onKeyDown={handleKeyDown}
        disabled={disabled}
        placeholder={disabled ? 'Executing...' : 'Type a command...'}
        autoFocus
        style={{
          flex: 1,
          backgroundColor: 'transparent',
          border: 'none',
          outline: 'none',
          color: '#e2e8f0',
          fontFamily: 'monospace',
          fontSize: 13,
          caretColor: '#6ee7b7',
          opacity: disabled ? 0.5 : 1,
        }}
      />
    </div>
  );
}
