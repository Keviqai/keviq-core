/**
 * Build a structured debug model from timeline events for InvocationDebugPanel.
 *
 * Extracts invocation lifecycle data from timeline events — no additional
 * API calls needed. All data comes from events already fetched by useRunTimeline.
 */

import type { TimelineEvent } from '@keviq/domain-types';

export interface ToolTurnSummary {
  turnIndex: number;
  toolCount: number;
  failureCount: number;
  modelLatencyMs: number | null;
  turnDurationMs: number | null;
  budgetRemainingMs: number | null;
  tools: Array<{ name: string; status: string; durationMs: number | null }>;
}

export type FailureCategory =
  | 'tool_failure'
  | 'malformed_tools'
  | 'budget_exhausted'
  | 'tool_rejected'
  | 'tool_cancelled'
  | 'transport_error'
  | 'gateway_error'
  | 'guardrail_rejected'
  | 'startup_error'
  | 'unknown';

export interface InvocationDebugModel {
  invocationId: string | null;
  terminalStatus: string | null;
  errorCode: string | null;
  errorMessage: string | null;
  failureCategory: FailureCategory | null;
  totalTurns: number;
  totalToolsCalled: number;
  totalToolFailures: number;
  totalModelLatencyMs: number | null;
  totalToolLatencyMs: number | null;
  terminalReason: string | null;
  promptTokens: number | null;
  completionTokens: number | null;
  turns: ToolTurnSummary[];
  humanControlEvents: Array<{ type: string; timestamp: string }>;
  hasData: boolean;
}

const FAILURE_CATEGORY_MAP: Record<string, FailureCategory> = {
  ALL_TOOLS_FAILED: 'tool_failure',
  MALFORMED_TOOL_CALLS: 'malformed_tools',
  BUDGET_EXHAUSTED: 'budget_exhausted',
  TOOL_REJECTED: 'tool_rejected',
  TOOL_CANCELLED: 'tool_cancelled',
  TRANSPORT_ERROR: 'transport_error',
  GATEWAY_ERROR: 'gateway_error',
  GUARDRAIL_REJECTED: 'guardrail_rejected',
  STARTUP_ERROR: 'startup_error',
  MISSING_PENDING_CONTEXT: 'startup_error',
};

const FAILURE_LABELS: Record<FailureCategory, string> = {
  tool_failure: 'Tool Failure',
  malformed_tools: 'Malformed Tool Calls',
  budget_exhausted: 'Budget Exhausted',
  tool_rejected: 'Tool Rejected by Reviewer',
  tool_cancelled: 'Cancelled by Operator',
  transport_error: 'Transport Error',
  gateway_error: 'Model Gateway Error',
  guardrail_rejected: 'Guardrail Rejected',
  startup_error: 'Startup Error',
  unknown: 'Unknown Error',
};

export function getFailureLabel(category: FailureCategory): string {
  return FAILURE_LABELS[category] ?? 'Unknown';
}

function num(val: unknown): number | null {
  return typeof val === 'number' ? val : null;
}

function str(val: unknown): string {
  return typeof val === 'string' ? val : '';
}

/**
 * Build debug model from a list of timeline events.
 * Filters for agent_invocation.* events and extracts structured data.
 */
export function buildInvocationDebugModel(events: TimelineEvent[]): InvocationDebugModel {
  const model: InvocationDebugModel = {
    invocationId: null,
    terminalStatus: null,
    errorCode: null,
    errorMessage: null,
    failureCategory: null,
    totalTurns: 0,
    totalToolsCalled: 0,
    totalToolFailures: 0,
    totalModelLatencyMs: null,
    totalToolLatencyMs: null,
    terminalReason: null,
    promptTokens: null,
    completionTokens: null,
    turns: [],
    humanControlEvents: [],
    hasData: false,
  };

  for (const evt of events) {
    const p = evt.payload ?? {};
    const type = evt.event_type;

    if (!type.startsWith('agent_invocation.')) continue;
    model.hasData = true;

    if (!model.invocationId && str(p.agent_invocation_id)) {
      model.invocationId = str(p.agent_invocation_id);
    }

    // Turn completed events
    if (type === 'agent_invocation.turn_completed') {
      const tools = (p.tools as Array<Record<string, unknown>> | undefined) ?? [];
      model.turns.push({
        turnIndex: num(p.turn_index) ?? model.turns.length,
        toolCount: num(p.tool_count) ?? 0,
        failureCount: num(p.failure_count) ?? 0,
        modelLatencyMs: num(p.model_latency_ms),
        turnDurationMs: num(p.turn_duration_ms),
        budgetRemainingMs: num(p.budget_remaining_ms),
        tools: tools.map((t) => ({
          name: str(t.name),
          status: str(t.status),
          durationMs: num(t.duration_ms),
        })),
      });
    }

    // Terminal events — extract summary
    if (type === 'agent_invocation.completed') {
      model.terminalStatus = 'completed';
      model.promptTokens = num(p.prompt_tokens);
      model.completionTokens = num(p.completion_tokens);
      const summary = p.invocation_summary as Record<string, unknown> | undefined;
      if (summary) {
        model.totalTurns = num(summary.total_turns) ?? model.turns.length;
        model.totalToolsCalled = num(summary.total_tools_called) ?? 0;
        model.totalToolFailures = num(summary.total_tool_failures) ?? 0;
        model.totalModelLatencyMs = num(summary.total_model_latency_ms);
        model.totalToolLatencyMs = num(summary.total_tool_latency_ms);
      }
    }

    if (type === 'agent_invocation.failed') {
      model.terminalStatus = 'failed';
      const detail = p.error_detail as Record<string, unknown> | undefined;
      if (detail) {
        model.errorCode = str(detail.error_code) || null;
        model.errorMessage = str(detail.error_message) || null;
        model.failureCategory = FAILURE_CATEGORY_MAP[model.errorCode ?? ''] ?? 'unknown';
        const summary = detail.invocation_summary as Record<string, unknown> | undefined;
        if (summary) {
          model.totalTurns = num(summary.total_turns) ?? model.turns.length;
          model.totalToolsCalled = num(summary.total_tools_called) ?? 0;
          model.totalToolFailures = num(summary.total_tool_failures) ?? 0;
          model.totalModelLatencyMs = num(summary.total_model_latency_ms);
          model.totalToolLatencyMs = num(summary.total_tool_latency_ms);
          model.terminalReason = str(summary.terminal_reason) || null;
        }
      }
    }

    if (type === 'agent_invocation.timed_out') {
      model.terminalStatus = 'timed_out';
      model.failureCategory = 'budget_exhausted';
      const detail = p.error_detail as Record<string, unknown> | undefined;
      if (detail) {
        model.errorCode = str(detail.error_code) || null;
        model.errorMessage = str(detail.error_message) || null;
        const summary = detail.invocation_summary as Record<string, unknown> | undefined;
        if (summary) {
          model.totalTurns = num(summary.total_turns) ?? model.turns.length;
          model.totalToolsCalled = num(summary.total_tools_called) ?? 0;
          model.totalModelLatencyMs = num(summary.total_model_latency_ms);
          model.totalToolLatencyMs = num(summary.total_tool_latency_ms);
          model.terminalReason = str(summary.terminal_reason) || null;
        }
      }
    }

    if (type === 'agent_invocation.cancelled') {
      model.terminalStatus = 'cancelled';
      const detail = p.error_detail as Record<string, unknown> | undefined;
      if (detail) {
        model.errorCode = str(detail.error_code) || null;
        model.errorMessage = str(detail.error_message) || null;
        model.failureCategory = FAILURE_CATEGORY_MAP[model.errorCode ?? ''] ?? null;
      }
    }

    // Human control events
    const humanEvents = [
      'agent_invocation.waiting_human',
      'agent_invocation.resumed',
      'agent_invocation.overridden',
      'agent_invocation.cancelled',
    ];
    if (humanEvents.includes(type)) {
      model.humanControlEvents.push({
        type: type.replace('agent_invocation.', ''),
        timestamp: evt.occurred_at,
      });
    }
  }

  // Derive totals from turns if summary wasn't present
  if (model.totalTurns === 0 && model.turns.length > 0) {
    model.totalTurns = model.turns.length;
    model.totalToolsCalled = model.turns.reduce((s, t) => s + t.toolCount, 0);
    model.totalToolFailures = model.turns.reduce((s, t) => s + t.failureCount, 0);
  }

  return model;
}
