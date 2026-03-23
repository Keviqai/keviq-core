/**
 * Extract structured detail rows from event payloads.
 *
 * Each event type maps to a set of label/value pairs that are
 * meaningful to users. Returns empty array for events with no
 * useful detail beyond what the summary already shows.
 */

import type { TimelineEvent } from '@keviq/domain-types';

export interface DetailRow {
  label: string;
  value: string;
  /** Optional execution_id for drill-down to ToolExecutionViewer */
  executionId?: string;
}

type Payload = Record<string, unknown>;

function str(val: unknown): string {
  return typeof val === 'string' ? val : '';
}

function num(val: unknown): number | null {
  return typeof val === 'number' ? val : null;
}

function formatDuration(ms: number): string {
  if (ms < 1000) return `${ms}ms`;
  if (ms < 60000) return `${(ms / 1000).toFixed(1)}s`;
  return `${(ms / 60000).toFixed(1)}min`;
}

const DETAIL_MAP: Record<string, (p: Payload, e: TimelineEvent) => DetailRow[]> = {
  'step.started': (p) => {
    const rows: DetailRow[] = [];
    if (str(p.instruction)) rows.push({ label: 'Instruction', value: str(p.instruction) });
    if (str(p.model_alias)) rows.push({ label: 'Model', value: str(p.model_alias) });
    return rows;
  },
  'step.completed': (p) => {
    const rows: DetailRow[] = [];
    const ms = num(p.duration_ms);
    if (ms !== null) rows.push({ label: 'Duration', value: formatDuration(ms) });
    if (str(p.output_summary)) rows.push({ label: 'Output', value: str(p.output_summary) });
    return rows;
  },
  'step.failed': (p) => {
    const rows: DetailRow[] = [];
    if (str(p.error_summary)) rows.push({ label: 'Error', value: str(p.error_summary) });
    if (str(p.error_detail)) rows.push({ label: 'Detail', value: str(p.error_detail).slice(0, 200) });
    const ms = num(p.duration_ms);
    if (ms !== null) rows.push({ label: 'Duration', value: formatDuration(ms) });
    return rows;
  },
  'run.completed': (p) => {
    const rows: DetailRow[] = [];
    const ms = num(p.duration_ms);
    if (ms !== null) rows.push({ label: 'Duration', value: formatDuration(ms) });
    return rows;
  },
  'run.failed': (p) => {
    const rows: DetailRow[] = [];
    if (str(p.error_summary)) rows.push({ label: 'Error', value: str(p.error_summary) });
    const ms = num(p.duration_ms);
    if (ms !== null) rows.push({ label: 'Duration', value: formatDuration(ms) });
    return rows;
  },
  'artifact.registered': (p) => {
    const rows: DetailRow[] = [];
    if (str(p.name)) rows.push({ label: 'Name', value: str(p.name) });
    if (str(p.artifact_type)) rows.push({ label: 'Type', value: str(p.artifact_type) });
    if (str(p.mime_type)) rows.push({ label: 'Format', value: str(p.mime_type) });
    return rows;
  },
  'artifact.ready': (p) => {
    const rows: DetailRow[] = [];
    if (str(p.name)) rows.push({ label: 'Name', value: str(p.name) });
    const size = num(p.size_bytes);
    if (size !== null) rows.push({ label: 'Size', value: size > 1024 ? `${(size / 1024).toFixed(1)} KB` : `${size} B` });
    return rows;
  },
  'sandbox.tool_execution.succeeded': (p) => {
    const rows: DetailRow[] = [];
    if (str(p.tool_name)) rows.push({ label: 'Tool', value: str(p.tool_name) });
    const ms = num(p.duration_ms);
    if (ms !== null) rows.push({ label: 'Duration', value: formatDuration(ms) });
    const exitCode = num(p.exit_code);
    if (exitCode !== null) rows.push({ label: 'Exit code', value: String(exitCode) });
    if (p.truncated === true) rows.push({ label: 'Output', value: 'Truncated' });
    const size = num(p.stdout_size_bytes);
    if (size !== null) rows.push({ label: 'Output size', value: size > 1024 ? `${(size / 1024).toFixed(1)} KB` : `${size} B` });
    if (str(p.execution_id)) rows.push({ label: 'Detail', value: 'View execution output', executionId: str(p.execution_id) });
    return rows;
  },
  'sandbox.tool_execution.failed': (p) => {
    const rows: DetailRow[] = [];
    if (str(p.tool_name)) rows.push({ label: 'Tool', value: str(p.tool_name) });
    if (str(p.error_code)) rows.push({ label: 'Error code', value: str(p.error_code) });
    if (str(p.error_message)) rows.push({ label: 'Error', value: str(p.error_message) });
    if (str(p.error) && !str(p.error_message)) rows.push({ label: 'Error', value: str(p.error) });
    const ms = num(p.duration_ms);
    if (ms !== null) rows.push({ label: 'Duration', value: formatDuration(ms) });
    const exitCode = num(p.exit_code);
    if (exitCode !== null) rows.push({ label: 'Exit code', value: String(exitCode) });
    if (str(p.execution_id)) rows.push({ label: 'Detail', value: 'View execution output', executionId: str(p.execution_id) });
    return rows;
  },
  'approval.requested': (p) => {
    const rows: DetailRow[] = [];
    if (str(p.prompt)) rows.push({ label: 'Prompt', value: str(p.prompt) });
    return rows;
  },
  'approval.decided': (p) => {
    const rows: DetailRow[] = [];
    if (str(p.decision)) rows.push({ label: 'Decision', value: str(p.decision) });
    if (str(p.comment)) rows.push({ label: 'Comment', value: str(p.comment) });
    return rows;
  },
  // O5: Tool approval events
  'tool_approval.requested': (p) => {
    const rows: DetailRow[] = [];
    if (str(p.tool_name)) rows.push({ label: 'Tool', value: str(p.tool_name) });
    if (str(p.risk_reason)) rows.push({ label: 'Risk', value: str(p.risk_reason) });
    if (str(p.invocation_id)) rows.push({ label: 'Invocation', value: str(p.invocation_id).slice(0, 8) + '...' });
    return rows;
  },
  'tool_approval.decided': (p) => {
    const rows: DetailRow[] = [];
    if (str(p.tool_name)) rows.push({ label: 'Tool', value: str(p.tool_name) });
    if (str(p.decision)) rows.push({ label: 'Decision', value: str(p.decision) });
    return rows;
  },
  'agent_invocation.waiting_human': (p) => {
    const rows: DetailRow[] = [];
    const detail = p.error_detail as Record<string, unknown> | undefined;
    const gatedTool = detail ? str(detail.gated_tool) : '';
    if (gatedTool) rows.push({ label: 'Gated tool', value: gatedTool });
    return rows;
  },
  'agent_invocation.overridden': () => [{ label: 'Action', value: 'Operator provided synthetic tool result' }],
  'agent_invocation.cancelled': (p) => {
    const rows: DetailRow[] = [];
    const detail = p.error_detail as Record<string, unknown> | undefined;
    if (detail && str(detail.error_code)) rows.push({ label: 'Reason', value: str(detail.error_message) });
    return rows;
  },
  // O6: Turn-level + invocation summary details
  'agent_invocation.turn_completed': (p) => {
    const rows: DetailRow[] = [];
    const idx = typeof p.turn_index === 'number' ? p.turn_index : null;
    if (idx !== null) rows.push({ label: 'Turn', value: String(idx + 1) });
    const tools = num(p.tool_count);
    if (tools !== null) rows.push({ label: 'Tools called', value: String(tools) });
    const fails = num(p.failure_count);
    if (fails !== null && fails > 0) rows.push({ label: 'Failures', value: String(fails) });
    const modelMs = num(p.model_latency_ms);
    if (modelMs !== null) rows.push({ label: 'Model latency', value: formatDuration(modelMs) });
    const turnMs = num(p.turn_duration_ms);
    if (turnMs !== null) rows.push({ label: 'Turn duration', value: formatDuration(turnMs) });
    const budget = num(p.budget_remaining_ms);
    if (budget !== null) rows.push({ label: 'Budget remaining', value: formatDuration(budget) });
    const toolList = p.tools as Array<Record<string, unknown>> | undefined;
    if (toolList && toolList.length > 0) {
      const summaries = toolList.map((t) => {
        const name = str(t.name);
        const status = str(t.status);
        const dur = num(t.duration_ms);
        return `${name}: ${status}${dur !== null ? ` (${formatDuration(dur)})` : ''}`;
      });
      rows.push({ label: 'Tools', value: summaries.join(', ') });
    }
    return rows;
  },
  'agent_invocation.completed': (p) => {
    const rows: DetailRow[] = [];
    const summary = p.invocation_summary as Record<string, unknown> | undefined;
    if (summary) {
      const turns = num(summary.total_turns);
      if (turns !== null) rows.push({ label: 'Total turns', value: String(turns) });
      const toolsCalled = num(summary.total_tools_called);
      if (toolsCalled !== null) rows.push({ label: 'Tools called', value: String(toolsCalled) });
      const toolFails = num(summary.total_tool_failures);
      if (toolFails !== null && toolFails > 0) rows.push({ label: 'Tool failures', value: String(toolFails) });
      const modelMs = num(summary.total_model_latency_ms);
      if (modelMs !== null) rows.push({ label: 'Model latency', value: formatDuration(modelMs) });
      const toolMs = num(summary.total_tool_latency_ms);
      if (toolMs !== null) rows.push({ label: 'Tool latency', value: formatDuration(toolMs) });
    }
    const prompt = num(p.prompt_tokens);
    const completion = num(p.completion_tokens);
    if (prompt !== null) rows.push({ label: 'Prompt tokens', value: String(prompt) });
    if (completion !== null) rows.push({ label: 'Completion tokens', value: String(completion) });
    return rows;
  },
  'agent_invocation.failed': (p) => {
    const rows: DetailRow[] = [];
    const detail = p.error_detail as Record<string, unknown> | undefined;
    if (detail) {
      if (str(detail.error_code)) rows.push({ label: 'Error code', value: str(detail.error_code) });
      if (str(detail.error_message)) rows.push({ label: 'Error', value: str(detail.error_message).slice(0, 200) });
      const turnNum = num(detail.turn);
      if (turnNum !== null) rows.push({ label: 'Failed at turn', value: String(turnNum + 1) });
      const summary = detail.invocation_summary as Record<string, unknown> | undefined;
      if (summary) {
        const turns = num(summary.total_turns);
        if (turns !== null) rows.push({ label: 'Total turns', value: String(turns) });
        const toolsCalled = num(summary.total_tools_called);
        if (toolsCalled !== null) rows.push({ label: 'Tools called', value: String(toolsCalled) });
        if (str(summary.terminal_reason)) rows.push({ label: 'Reason', value: str(summary.terminal_reason) });
      }
    }
    return rows;
  },
  'agent_invocation.timed_out': (p) => {
    const rows: DetailRow[] = [];
    const detail = p.error_detail as Record<string, unknown> | undefined;
    if (detail) {
      if (str(detail.error_code)) rows.push({ label: 'Error code', value: str(detail.error_code) });
      const turnsCompleted = num(detail.turns_completed);
      if (turnsCompleted !== null) rows.push({ label: 'Turns completed', value: String(turnsCompleted) });
      if (str(detail.error_message)) rows.push({ label: 'Detail', value: str(detail.error_message).slice(0, 200) });
      const summary = detail.invocation_summary as Record<string, unknown> | undefined;
      if (summary) {
        const modelMs = num(summary.total_model_latency_ms);
        if (modelMs !== null) rows.push({ label: 'Model latency', value: formatDuration(modelMs) });
        const toolMs = num(summary.total_tool_latency_ms);
        if (toolMs !== null) rows.push({ label: 'Tool latency', value: formatDuration(toolMs) });
        if (str(summary.terminal_reason)) rows.push({ label: 'Reason', value: str(summary.terminal_reason) });
      }
    }
    return rows;
  },
  'terminal.command.executed': (p) => {
    const rows: DetailRow[] = [];
    if (str(p.command)) rows.push({ label: 'Command', value: str(p.command) });
    const code = num(p.exit_code);
    if (code !== null) rows.push({ label: 'Exit code', value: String(code) });
    return rows;
  },
};

export function getEventDetails(event: TimelineEvent): DetailRow[] {
  const fn = DETAIL_MAP[event.event_type];
  if (!fn) return [];
  return fn(event.payload ?? {}, event);
}
