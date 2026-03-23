export function setAuthCookie(token: string): void {
  document.cookie = `access_token=${token}; path=/; SameSite=Lax`;
}

export function clearAuthCookie(): void {
  document.cookie = 'access_token=; path=/; expires=Thu, 01 Jan 1970 00:00:00 GMT';
}
