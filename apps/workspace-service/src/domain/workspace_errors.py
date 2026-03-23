"""Workspace domain errors."""


class WorkspaceError(Exception):
    pass


class WorkspaceNotFound(WorkspaceError):
    def __init__(self, workspace_id: str):
        super().__init__(f"Workspace not found: {workspace_id}")
        self.workspace_id = workspace_id


class SlugAlreadyExists(WorkspaceError):
    def __init__(self, slug: str):
        super().__init__(f"Slug already taken: {slug}")
        self.slug = slug


class MemberNotFound(WorkspaceError):
    def __init__(self, workspace_id: str, user_id: str):
        super().__init__(f"Member not found: user {user_id} in workspace {workspace_id}")


class MemberAlreadyExists(WorkspaceError):
    def __init__(self, workspace_id: str, user_id: str):
        super().__init__(f"User {user_id} already a member of workspace {workspace_id}")


class InvalidRole(WorkspaceError):
    def __init__(self, role: str):
        super().__init__(f"Invalid role: {role}")
