"""Auth domain errors."""


class AuthError(Exception):
    pass


class EmailAlreadyExists(AuthError):
    def __init__(self, email: str):
        super().__init__(f"Email already registered: {email}")
        self.email = email


class InvalidCredentials(AuthError):
    def __init__(self):
        super().__init__("Invalid email or password")


class UserNotFound(AuthError):
    def __init__(self, user_id: str):
        super().__init__(f"User not found: {user_id}")
        self.user_id = user_id
