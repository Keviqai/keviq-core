export function hasCapability(
  capabilities: Record<string, boolean> | undefined,
  cap: string,
): boolean {
  return capabilities?.[cap] === true;
}
