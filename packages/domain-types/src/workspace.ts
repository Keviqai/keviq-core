export interface Workspace {
  id: string;
  slug: string;
  display_name: string;
  owner_id: string;
  created_at: string;
  _capabilities?: string[];
}

export interface WorkspaceMember {
  id: string;
  user_id: string;
  workspace_id: string;
  role: string;
  joined_at: string;
  updated_at: string;
  invited_by_id: string | null;
  display_name: string | null;
  email: string | null;
}
