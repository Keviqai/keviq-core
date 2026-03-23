'use client';

import { useEffect, useRef, useState } from 'react';
import type { TimelineEvent } from '@keviq/domain-types';
import { TimelineItem } from './timeline-item';

export const EMPTY_TIMELINE_EVENTS: TimelineEvent[] = [];

const NEAR_BOTTOM_THRESHOLD = 200; // px from page bottom to count as "near bottom"

function isNearBottom(): boolean {
  if (typeof window === 'undefined') return true;
  return (
    window.scrollY + window.innerHeight >=
    document.documentElement.scrollHeight - NEAR_BOTTOM_THRESHOLD
  );
}

export function TimelineFeed({ events, onSelectExecution, memberMap }: { events: TimelineEvent[]; onSelectExecution?: (id: string) => void; memberMap?: Map<string, string> }) {
  const bottomRef = useRef<HTMLDivElement>(null);
  const prevCountRef = useRef(events.length);
  const [pendingCount, setPendingCount] = useState(0);

  useEffect(() => {
    const prev = prevCountRef.current;
    const added = events.length - prev;
    prevCountRef.current = events.length;

    if (added <= 0) return;

    if (isNearBottom()) {
      bottomRef.current?.scrollIntoView({ behavior: 'smooth', block: 'end' });
      setPendingCount(0);
    } else {
      setPendingCount((n) => n + added);
    }
  }, [events.length]);

  function scrollToBottom() {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth', block: 'end' });
    setPendingCount(0);
  }

  if (events.length === 0) {
    return (
      <p style={{ color: '#9ca3af', fontSize: 13, fontStyle: 'italic' }}>
        No timeline events yet.
      </p>
    );
  }

  return (
    <div style={{ position: 'relative' }}>
      <div style={{ display: 'flex', flexDirection: 'column', gap: 0 }}>
        {events.map((event) => (
          <TimelineItem key={event.event_id} event={event} onSelectExecution={onSelectExecution} memberMap={memberMap} />
        ))}
      </div>
      <div ref={bottomRef} />

      {pendingCount > 0 && (
        <button
          onClick={scrollToBottom}
          style={{
            position: 'sticky',
            bottom: 12,
            display: 'flex',
            alignItems: 'center',
            gap: 4,
            margin: '8px auto 0',
            padding: '4px 12px',
            backgroundColor: '#1d4ed8',
            color: '#fff',
            border: 'none',
            borderRadius: 9999,
            fontSize: 12,
            fontWeight: 500,
            cursor: 'pointer',
            boxShadow: '0 2px 8px rgba(0,0,0,0.15)',
          }}
        >
          ↓ {pendingCount} new event{pendingCount !== 1 ? 's' : ''}
        </button>
      )}
    </div>
  );
}
