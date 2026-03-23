import type { WorkspaceMember } from '@keviq/domain-types';

/**
 * Resolve a user_id to a human-readable display name.
 *
 * Priority: display_name > email > truncated UUID fallback.
 * Returns '—' for null/undefined userId.
 * Returns truncated UUID when members list is not yet loaded.
 */
export function resolveDisplayName(
  userId: string | null | undefined,
  members: WorkspaceMember[] | undefined,
): string {
  if (!userId) return '—';
  if (!members) return userId.slice(0, 8) + '…';
  const member = members.find((m) => m.user_id === userId);
  if (!member) return userId.slice(0, 8) + '…';
  return member.display_name || member.email || userId.slice(0, 8) + '…';
}
