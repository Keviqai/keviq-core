"""Secret domain exceptions."""


class SecretError(Exception):
    """Base exception for secret-broker domain."""


class SecretNotFound(SecretError):
    """Raised when a secret does not exist."""

    def __init__(self, secret_id: str) -> None:
        super().__init__(f'Secret not found: {secret_id}')
        self.secret_id = secret_id
