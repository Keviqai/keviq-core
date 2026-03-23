'use client';

import { useMemo } from 'react';
import { useWorkspaces } from '@keviq/server-state';

const EMPTY_CAPS: string[] = [];

/**
 * Returns the server-derived capabilities array for the given workspace.
 * Capabilities are resolved from the user's role — never derive from role strings locally.
 */
export function useWorkspaceCapabilities(workspaceId: string): {
  capabilities: string[];
  isLoading: boolean;
} {
  const { data: workspaces, isLoading } = useWorkspaces();
  const capabilities = useMemo(() => {
    const workspace = workspaces?.find((w) => w.id === workspaceId);
    return workspace?._capabilities ?? EMPTY_CAPS;
  }, [workspaces, workspaceId]);
  return { capabilities, isLoading };
}
