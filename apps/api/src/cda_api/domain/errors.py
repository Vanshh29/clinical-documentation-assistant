class DomainError(Exception):
    """Base class for errors raised by domain and application logic."""


class InvalidTransition(DomainError):
    def __init__(self, current: str, target: str) -> None:
        super().__init__(f"Cannot move note from {current} to {target}")
        self.current = current
        self.target = target


class NotFound(DomainError):
    pass


class Forbidden(DomainError):
    pass


class AuthenticationFailed(DomainError):
    pass


class ValidationFailed(DomainError):
    pass
