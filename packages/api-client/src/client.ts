export interface ApiClient {
  get: <T>(path: string) => Promise<T>;
  post: <T>(path: string, body?: unknown) => Promise<T>;
  postForm: <T>(path: string, formData: FormData) => Promise<T>;
  put: <T>(path: string, body?: unknown) => Promise<T>;
  patch: <T>(path: string, body?: unknown) => Promise<T>;
  delete: <T>(path: string) => Promise<T>;
}

function getTokenFromCookie(): string | undefined {
  if (typeof document === 'undefined') return undefined;
  return document.cookie.match(/(?:^|;\s*)access_token=([^;]+)/)?.[1];
}

/**
 * Global 401 handler: when any API call returns 401 (except login/register),
 * clear the expired token cookie and redirect to login.
 * Uses a flag to prevent multiple concurrent redirects.
 */
let _redirecting = false;
function handleExpiredSession(status: number, path: string): void {
  if (
    status !== 401 ||
    _redirecting ||
    typeof window === 'undefined' ||
    window.location.pathname.startsWith('/login') ||
    window.location.pathname.startsWith('/register') ||
    path.includes('/auth/login') ||
    path.includes('/auth/register')
  ) {
    return;
  }
  _redirecting = true;
  document.cookie = 'access_token=; path=/; expires=Thu, 01 Jan 1970 00:00:00 GMT; SameSite=Lax';

  // Show a visible notification before redirecting so user isn't surprised
  try {
    const banner = document.createElement('div');
    banner.setAttribute('role', 'alert');
    banner.textContent = 'Your session has expired. Redirecting to login...';
    Object.assign(banner.style, {
      position: 'fixed', top: '0', left: '0', right: '0', zIndex: '99999',
      padding: '12px 16px', backgroundColor: '#fef3c7', color: '#92400e',
      fontSize: '14px', fontWeight: '600', textAlign: 'center',
      borderBottom: '2px solid #f59e0b',
    });
    document.body.appendChild(banner);
  } catch { /* ignore DOM errors */ }

  setTimeout(() => { window.location.replace('/login'); }, 2000);
}

export function createApiClient(baseUrl: string): ApiClient {
  async function request<T>(method: string, path: string, body?: unknown): Promise<T> {
    const token = getTokenFromCookie();
    const headers: Record<string, string> = {};
    if (body) headers['Content-Type'] = 'application/json';
    if (token) headers['Authorization'] = `Bearer ${token}`;

    const res = await fetch(`${baseUrl}${path}`, {
      method,
      headers,
      credentials: 'include',
      body: body ? JSON.stringify(body) : undefined,
    });

    if (!res.ok) {
      handleExpiredSession(res.status, path);
      const error = await res.json().catch(() => ({ message: res.statusText })) as { message?: string };
      throw new ApiClientError(res.status, error.message ?? res.statusText, error);
    }

    if (res.status === 204) {
      return undefined as T;
    }

    return res.json() as Promise<T>;
  }

  async function formRequest<T>(path: string, formData: FormData): Promise<T> {
    const token = getTokenFromCookie();
    const res = await fetch(`${baseUrl}${path}`, {
      method: 'POST',
      headers: token ? { 'Authorization': `Bearer ${token}` } : {},
      credentials: 'include',
      body: formData,
    });

    if (!res.ok) {
      handleExpiredSession(res.status, path);
      const error = await res.json().catch(() => ({ message: res.statusText })) as { message?: string };
      throw new ApiClientError(res.status, error.message ?? res.statusText, error);
    }

    return res.json() as Promise<T>;
  }

  return {
    get: <T>(path: string) => request<T>('GET', path),
    post: <T>(path: string, body?: unknown) => request<T>('POST', path, body),
    postForm: <T>(path: string, formData: FormData) => formRequest<T>(path, formData),
    put: <T>(path: string, body?: unknown) => request<T>('PUT', path, body),
    patch: <T>(path: string, body?: unknown) => request<T>('PATCH', path, body),
    delete: <T>(path: string) => request<T>('DELETE', path),
  };
}

export class ApiClientError extends Error {
  constructor(
    public readonly status: number,
    message: string,
    public readonly body: unknown,
  ) {
    super(message);
    this.name = 'ApiClientError';
  }
}
