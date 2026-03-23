'use client';

import { useEffect, useRef, useMemo, useState } from 'react';
import type { TimelineEvent } from '@keviq/domain-types';

export type ConnectionStatus = 'connecting' | 'live' | 'reconnecting' | 'disconnected';

export interface EventStreamOptions {
  workspaceId: string;
  scope?: { type: 'run'; id: string } | { type: 'workspace' };
  onEvent?: (event: TimelineEvent) => void;
  onInvalidate?: (event: TimelineEvent) => void;
}

export interface EventStreamState {
  connected: boolean;
  status: ConnectionStatus;
  lastEventId: string | null;
}

const API_URL = typeof window !== 'undefined'
  ? (window as unknown as Record<string, unknown>).__MONA_API_URL as string ?? ''
  : '';

const RECONNECT_BASE_MS = 1000;
const RECONNECT_MAX_MS = 30000;

/** Read JWT from the access_token cookie for SSE auth (EventSource cannot send headers). */
function getTokenFromCookie(): string | undefined {
  if (typeof document === 'undefined') return undefined;
  return document.cookie.match(/(?:^|;\s*)access_token=([^;]+)/)?.[1];
}

export function useEventStream(options: EventStreamOptions): EventStreamState {
  const { workspaceId, scope, onEvent, onInvalidate } = options;
  const [status, setStatus] = useState<ConnectionStatus>('disconnected');
  const lastEventIdRef = useRef<string | null>(null);
  const retriesRef = useRef(0);
  const eventSourceRef = useRef<EventSource | null>(null);

  // Stable callback refs
  const onEventRef = useRef(onEvent);
  onEventRef.current = onEvent;
  const onInvalidateRef = useRef(onInvalidate);
  onInvalidateRef.current = onInvalidate;

  // FIX P3: Serialize scope to a stable string key so object identity doesn't matter
  const scopeKey = useMemo(() => {
    if (!scope) return 'workspace';
    if (scope.type === 'run') return `run:${scope.id}`;
    return 'workspace';
  }, [scope?.type, scope?.type === 'run' ? scope.id : undefined]);

  useEffect(() => {
    if (typeof window === 'undefined' || !workspaceId) return;

    let reconnectTimer: ReturnType<typeof setTimeout> | null = null;
    let disposed = false;

    // FIX B03: Reset lastEventId when scope/workspace changes
    lastEventIdRef.current = null;
    retriesRef.current = 0;

    function buildUrl() {
      const token = getTokenFromCookie();
      if (scopeKey.startsWith('run:')) {
        const runId = scopeKey.slice(4);
        // workspace_id required by gateway auth + backend workspace isolation
        const base = `${API_URL}/v1/runs/${encodeURIComponent(runId)}/events/stream?workspace_id=${encodeURIComponent(workspaceId)}`;
        return token ? `${base}&token=${encodeURIComponent(token)}` : base;
      }
      const base = `${API_URL}/v1/workspaces/${encodeURIComponent(workspaceId)}/events/stream`;
      return token ? `${base}?token=${encodeURIComponent(token)}` : base;
    }

    function connect() {
      if (disposed) return;

      const url = buildUrl();
      const fullUrl = lastEventIdRef.current
        ? `${url}${url.includes('?') ? '&' : '?'}last_event_id=${encodeURIComponent(lastEventIdRef.current)}`
        : url;

      setStatus(retriesRef.current > 0 ? 'reconnecting' : 'connecting');

      const es = new EventSource(fullUrl, { withCredentials: true });
      eventSourceRef.current = es;

      es.onopen = () => {
        if (disposed) return;
        retriesRef.current = 0;
        setStatus('live');
      };

      // FIX P2: Use only named event listeners (backend sends `event:<type>`).
      // Remove onmessage to avoid duplicate dispatch.
      const eventTypes = [
        // Task lifecycle
        'task.submitted', 'task.started', 'task.completed', 'task.failed',
        'task.cancelled', 'task.recovered', 'task.retried',
        // Run lifecycle
        'run.queued', 'run.started', 'run.completing', 'run.completed',
        'run.failed', 'run.cancelled', 'run.timed_out', 'run.recovered',
        // Step lifecycle
        'step.started', 'step.completed', 'step.failed', 'step.cancelled', 'step.recovered',
        // Artifact lifecycle
        'artifact.registered', 'artifact.writing', 'artifact.ready',
        'artifact.failed', 'artifact.lineage_recorded',
        // Approval
        'approval.requested', 'approval.decided',
        // Sandbox + tool execution
        'sandbox.provisioned', 'sandbox.provision_failed', 'sandbox.terminated',
        'sandbox.tool_execution.requested', 'sandbox.tool_execution.succeeded',
        'sandbox.tool_execution.failed',
        // Terminal
        'terminal.command.executed',
      ];
      for (const eventType of eventTypes) {
        es.addEventListener(eventType, (msg) => {
          if (disposed) return;
          handleMessage(msg as MessageEvent);
        });
      }

      es.onerror = () => {
        if (disposed) return;
        es.close();
        eventSourceRef.current = null;
        setStatus('reconnecting');
        scheduleReconnect();
      };
    }

    function handleMessage(msg: MessageEvent) {
      if (msg.lastEventId) {
        lastEventIdRef.current = msg.lastEventId;
      }

      let event: TimelineEvent;
      try {
        event = JSON.parse(msg.data);
      } catch {
        return; // Skip malformed events (heartbeats, etc.)
      }

      onEventRef.current?.(event);
      onInvalidateRef.current?.(event);
    }

    function scheduleReconnect() {
      if (disposed) return;
      const delay = Math.min(
        RECONNECT_BASE_MS * Math.pow(2, retriesRef.current),
        RECONNECT_MAX_MS,
      );
      retriesRef.current += 1;
      reconnectTimer = setTimeout(connect, delay);
    }

    connect();

    return () => {
      disposed = true;
      if (reconnectTimer) clearTimeout(reconnectTimer);
      if (eventSourceRef.current) {
        eventSourceRef.current.close();
        eventSourceRef.current = null;
      }
      // FIX B05: Don't call setStatus after unmount — disposed flag prevents
      // state updates in event handlers, but this direct call is safe because
      // React ignores setState on unmounted components in React 18+.
    };
  }, [workspaceId, scopeKey]);

  return {
    connected: status === 'live',
    status,
    lastEventId: lastEventIdRef.current,
  };
}
