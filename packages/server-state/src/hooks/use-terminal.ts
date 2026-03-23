'use client';

import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { createTerminalApi } from '@keviq/api-client';
import type { CreateTerminalSessionRequest, ExecCommandRequest } from '@keviq/api-client';
import { apiClient } from '../api';
import { queryKeys } from '../query-keys';

const terminalApi = createTerminalApi(apiClient);

export function useTerminalSession(sessionId: string | null) {
  return useQuery({
    queryKey: queryKeys.terminal.session(sessionId ?? ''),
    queryFn: () => terminalApi.getSession(sessionId!),
    enabled: !!sessionId,
  });
}

export function useTerminalHistory(sessionId: string | null) {
  return useQuery({
    queryKey: queryKeys.terminal.history(sessionId ?? ''),
    queryFn: () => terminalApi.getHistory(sessionId!),
    enabled: !!sessionId,
  });
}

export function useCreateTerminalSession() {
  return useMutation({
    mutationFn: (req: CreateTerminalSessionRequest) =>
      terminalApi.createSession(req),
  });
}

export function useExecCommand(sessionId: string) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (req: ExecCommandRequest) =>
      terminalApi.execCommand(sessionId, req),
    onSuccess: () => {
      qc.invalidateQueries({
        queryKey: queryKeys.terminal.history(sessionId),
      });
    },
  });
}

export function useCloseTerminalSession() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (sessionId: string) => terminalApi.closeSession(sessionId),
    onSuccess: (_data, sessionId) => {
      qc.invalidateQueries({
        queryKey: queryKeys.terminal.session(sessionId),
      });
    },
  });
}
