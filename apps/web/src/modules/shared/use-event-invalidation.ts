'use client';

import { useCallback, useRef, useEffect } from 'react';
import { useQueryClient } from '@tanstack/react-query';
import type { TimelineEvent } from '@keviq/domain-types';
import { queryKeys } from '@keviq/server-state';

/**
 * Returns an onInvalidate callback that maps SSE events to query invalidations.
 * SSE only triggers refetch — it never sets query data directly (S6-G1, S6-G2).
 *
 * FIX P1: Collects query keys over a 150ms window, then batch-invalidates once.
 * This prevents invalidation storms when multiple SSE events arrive in rapid succession.
 */
export function useEventInvalidation() {
  const queryClient = useQueryClient();
  const pendingKeysRef = useRef<Set<string>>(new Set());
  const timerRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  // Cleanup timer on unmount
  useEffect(() => {
    return () => {
      if (timerRef.current) clearTimeout(timerRef.current);
    };
  }, []);

  return useCallback(
    (event: TimelineEvent) => {
      const { event_type, workspace_id, task_id, run_id } = event;

      // Collect serialized query keys into a set (deduplicates naturally)
      function enqueue(key: readonly unknown[]) {
        pendingKeysRef.current.add(JSON.stringify(key));
      }

      // Always invalidate the timeline for the relevant entity
      if (task_id) {
        enqueue(queryKeys.timeline.task(task_id));
      }
      if (run_id) {
        enqueue(queryKeys.timeline.run(run_id));
      }

      // Map event families to entity queries
      if (event_type.startsWith('task.') && task_id) {
        enqueue(queryKeys.tasks.detail(task_id));
        enqueue(queryKeys.tasks.list(workspace_id));
      }

      if (event_type.startsWith('run.') && run_id) {
        enqueue(queryKeys.runs.detail(run_id));
        if (task_id) {
          enqueue(queryKeys.runs.listByTask(task_id));
        }
      }

      if (event_type.startsWith('step.') && run_id) {
        enqueue(queryKeys.steps.listByRun(run_id));
        enqueue(queryKeys.runs.detail(run_id));
      }

      if (event_type.startsWith('artifact.')) {
        enqueue(queryKeys.artifacts.list(workspace_id));
      }

      if (event_type.startsWith('approval.') || event_type.startsWith('tool_approval.')) {
        enqueue(queryKeys.approvals.list(workspace_id));
        enqueue(queryKeys.approvals.count(workspace_id));
      }

      // O5: Agent invocation human control events → refresh task/run
      if (event_type.startsWith('agent_invocation.')) {
        if (task_id) {
          enqueue(queryKeys.tasks.detail(task_id));
          enqueue(queryKeys.tasks.list(workspace_id));
        }
        if (run_id) {
          enqueue(queryKeys.runs.detail(run_id));
        }
      }

      // Schedule flush if not already pending
      if (!timerRef.current) {
        timerRef.current = setTimeout(() => {
          const keys = pendingKeysRef.current;
          pendingKeysRef.current = new Set();
          timerRef.current = null;

          for (const serialized of keys) {
            queryClient.invalidateQueries({ queryKey: JSON.parse(serialized) });
          }
        }, 150);
      }
    },
    [queryClient],
  );
}
