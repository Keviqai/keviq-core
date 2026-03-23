/**
 * Build a user_id → display_name map from workspace members.
 * Used by timeline actor labels and other name resolution surfaces.
 */

import type { WorkspaceMember } from '@keviq/domain-types';

export function buildMemberMap(members: WorkspaceMember[] | undefined): Map<string, string> | undefined {
  if (!members || members.length === 0) return undefined;
  const map = new Map<string, string>();
  for (const m of members) {
    const name = m.display_name || m.email || m.user_id.slice(0, 8) + '…';
    map.set(m.user_id, name);
  }
  return map;
}
