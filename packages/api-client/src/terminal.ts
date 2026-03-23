import type { ApiClient } from './client';
import type { TerminalSession, CommandResult } from '@keviq/domain-types';

export interface CreateTerminalSessionRequest {
  sandbox_id: string;
  run_id: string;
  workspace_id: string;
}

export interface ExecCommandRequest {
  command: string;
  timeout_s?: number;
}

export interface TerminalApi {
  createSession: (req: CreateTerminalSessionRequest) => Promise<TerminalSession>;
  execCommand: (sessionId: string, req: ExecCommandRequest) => Promise<CommandResult>;
  getSession: (sessionId: string) => Promise<TerminalSession>;
  getHistory: (sessionId: string) => Promise<{ items: CommandResult[] }>;
  closeSession: (sessionId: string) => Promise<TerminalSession>;
}

export function createTerminalApi(client: ApiClient): TerminalApi {
  return {
    createSession: (req) =>
      client.post('/v1/terminal/sessions', req),
    execCommand: (sessionId, req) =>
      client.post(
        `/v1/terminal/sessions/${encodeURIComponent(sessionId)}/exec`,
        req,
      ),
    getSession: (sessionId) =>
      client.get(`/v1/terminal/sessions/${encodeURIComponent(sessionId)}`),
    getHistory: (sessionId) =>
      client.get(`/v1/terminal/sessions/${encodeURIComponent(sessionId)}/history`),
    closeSession: (sessionId) =>
      client.post(`/v1/terminal/sessions/${encodeURIComponent(sessionId)}/close`, {}),
  };
}
