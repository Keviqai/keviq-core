/**
 * Human-readable event summaries and actor labels for timeline display.
 *
 * Generates user-friendly text from event payloads. Falls back gracefully
 * when payload fields are missing.
 */

import type { TimelineEvent } from '@keviq/domain-types';

const ACTOR_ICONS: Record<string, string> = {
  user: '\u{1F464}',      // 👤
  agent: '\u{1F916}',     // 🤖
  system: '\u{2699}\uFE0F', // ⚙️
  scheduler: '\u{1F552}', // 🕒
};

export function getActorLabel(
  actor: { type: string; id: string } | undefined,
  memberMap?: Map<string, string>,
): string | null {
  if (!actor?.type) return null;
  const icon = ACTOR_ICONS[actor.type] ?? '';
  // If actor is a user and we have a member name map, show the name
  if (actor.type === 'user' && memberMap) {
    const name = memberMap.get(actor.id);
    if (name) return `${icon} ${name}`;
  }
  return `${icon} ${actor.type}`;
}

type Payload = Record<string, unknown>;

function str(val: unknown): string {
  return typeof val === 'string' ? val : '';
}

function formatMs(ms: number): string {
  if (ms < 1000) return `${ms}ms`;
  if (ms < 60000) return `${(ms / 1000).toFixed(1)}s`;
  return `${(ms / 60000).toFixed(1)}min`;
}

const SUMMARY_MAP: Record<string, (p: Payload) => string> = {
  'task.submitted': () => 'Submitted for execution',
  'task.started': () => 'Agent began processing',
  'task.completed': () => 'Task finished successfully',
  'task.failed': (p) => str(p.error_summary) || 'Task execution failed',
  'task.cancelled': () => 'Task was cancelled',
  'task.recovered': () => 'Task recovered from stuck state',

  'run.queued': () => 'Run queued for execution',
  'run.started': () => 'Run execution started',
  'run.completing': () => 'Run finalizing results',
  'run.completed': (p) => {
    const ms = p.duration_ms;
    return ms ? `Completed in ${Number(ms)}ms` : 'Run completed successfully';
  },
  'run.failed': (p) => str(p.error_summary) || 'Run failed',
  'run.cancelled': () => 'Run was cancelled',
  'run.timed_out': () => 'Run exceeded time limit',
  'run.recovered': () => 'Run recovered from stuck state',

  'step.started': (p) => str(p.instruction)
    ? `Started: ${str(p.instruction).slice(0, 60)}${str(p.instruction).length > 60 ? '…' : ''}`
    : 'Step execution started',
  'step.completed': (p) => {
    const ms = p.duration_ms;
    return ms ? `Step completed in ${Number(ms)}ms` : 'Step completed';
  },
  'step.failed': (p) => str(p.error_summary) || 'Step failed',
  'step.cancelled': () => 'Step was cancelled',
  'step.recovered': () => 'Step recovered',

  'artifact.registered': (p) => str(p.name) ? `Artifact "${str(p.name)}" registered` : 'Artifact registered',
  'artifact.writing': (p) => str(p.name) ? `Writing "${str(p.name)}"` : 'Writing artifact',
  'artifact.ready': (p) => str(p.name) ? `"${str(p.name)}" ready` : 'Artifact ready',
  'artifact.failed': (p) => str(p.name) ? `"${str(p.name)}" failed` : 'Artifact failed',
  'artifact.lineage_recorded': () => 'Lineage relationship recorded',

  'approval.requested': (p) => str(p.prompt) ? `Approval: ${str(p.prompt).slice(0, 60)}` : 'Approval requested',
  'approval.decided': (p) => str(p.decision) ? `Approval ${str(p.decision)}` : 'Approval decision made',

  // O5: Tool approval events
  'tool_approval.requested': (p) => str(p.tool_name)
    ? `Waiting for approval: ${str(p.tool_name)}`
    : 'Tool approval requested',
  'tool_approval.decided': (p) => {
    const tool = str(p.tool_name);
    const decision = str(p.decision);
    if (tool && decision) return `Tool "${tool}" ${decision}`;
    return decision ? `Tool ${decision}` : 'Tool approval decided';
  },

  // O5: Agent invocation human control events
  'agent_invocation.waiting_human': (p) => str(p.gated_tool)
    ? `Paused: awaiting approval for ${str(p.gated_tool)}`
    : 'Paused: awaiting human approval',
  'agent_invocation.resumed': () => 'Resumed after approval',
  'agent_invocation.overridden': () => 'Resumed with operator override',
  'agent_invocation.cancelled': (p) => {
    const detail = p.error_detail as Record<string, unknown> | undefined;
    return detail && str(detail.error_code) === 'TOOL_CANCELLED'
      ? 'Cancelled by operator during tool approval'
      : 'Invocation cancelled';
  },

  // O6: Agent invocation lifecycle + observability events
  'agent_invocation.started': () => 'Invocation started',
  'agent_invocation.waiting_tool': (p) => {
    const tc = p.tool_calls as unknown[];
    return tc && tc.length > 0
      ? `Dispatching ${tc.length} tool(s)`
      : 'Dispatching tools';
  },
  'agent_invocation.turn_completed': (p) => {
    const idx = typeof p.turn_index === 'number' ? p.turn_index + 1 : '?';
    const tools = typeof p.tool_count === 'number' ? p.tool_count : 0;
    const fails = typeof p.failure_count === 'number' ? p.failure_count : 0;
    const budget = typeof p.budget_remaining_ms === 'number' ? p.budget_remaining_ms : null;
    let text = `Turn ${idx}: ${tools} tool(s)`;
    if (fails > 0) text += ` (${fails} failed)`;
    if (budget !== null) text += `, ${formatMs(budget)} remaining`;
    return text;
  },
  'agent_invocation.completed': (p) => {
    const summary = p.invocation_summary as Record<string, unknown> | undefined;
    if (summary) {
      const turns = typeof summary.total_turns === 'number' ? summary.total_turns : 0;
      const tokens = (typeof p.prompt_tokens === 'number' ? p.prompt_tokens : 0)
        + (typeof p.completion_tokens === 'number' ? p.completion_tokens : 0);
      return turns > 0
        ? `Completed (${turns} turn${turns > 1 ? 's' : ''}, ${tokens} tokens)`
        : `Completed (${tokens} tokens)`;
    }
    return 'Invocation completed';
  },
  'agent_invocation.failed': (p) => {
    const detail = p.error_detail as Record<string, unknown> | undefined;
    if (detail) {
      const code = str(detail.error_code);
      const msg = str(detail.error_message);
      if (code) return `Failed: ${code}${msg ? ' — ' + msg.slice(0, 80) : ''}`;
    }
    return 'Invocation failed';
  },
  'agent_invocation.timed_out': (p) => {
    const detail = p.error_detail as Record<string, unknown> | undefined;
    if (detail) {
      const turns = typeof detail.turns_completed === 'number' ? detail.turns_completed : null;
      return turns !== null
        ? `Timed out after ${turns} turn(s)`
        : 'Invocation timed out';
    }
    return 'Invocation timed out';
  },

  'sandbox.provisioned': () => 'Execution sandbox ready',
  'sandbox.provision_failed': (p) => str(p.error) || 'Sandbox provisioning failed',
  'sandbox.terminated': () => 'Sandbox terminated',

  'sandbox.tool_execution.requested': (p) => str(p.tool_name) ? `Tool: ${str(p.tool_name)}` : 'Tool execution requested',
  'sandbox.tool_execution.succeeded': (p) => str(p.tool_name) ? `Tool "${str(p.tool_name)}" succeeded` : 'Tool executed',
  'sandbox.tool_execution.failed': (p) => str(p.tool_name) ? `Tool "${str(p.tool_name)}" failed` : 'Tool execution failed',

  'terminal.command.executed': (p) => str(p.command) ? `$ ${str(p.command).slice(0, 50)}` : 'Terminal command executed',
};

export function getEventSummary(event: TimelineEvent): string | null {
  const fn = SUMMARY_MAP[event.event_type];
  if (!fn) return null;
  return fn(event.payload ?? {});
}
