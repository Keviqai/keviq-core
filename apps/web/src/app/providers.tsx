'use client';

import { ServerStateProvider } from '@keviq/server-state';
import type { ReactNode } from 'react';

export function Providers({ children }: { children: ReactNode }) {
  return <ServerStateProvider>{children}</ServerStateProvider>;
}
