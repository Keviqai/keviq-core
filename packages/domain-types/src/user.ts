import type { Workspace } from './workspace';

export interface User {
  id: string;
  email: string;
  display_name: string;
  created_at: string;
  last_active_at: string | null;
}

export interface AuthSession {
  user: User;
  access_token: string;
  workspaces: Workspace[];
}
