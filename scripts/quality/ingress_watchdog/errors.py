"""Typed failures for watchdog protocol and state transitions."""


class WatchdogError(Exception):
    """Base error for watchdog failures."""


class ProtocolError(WatchdogError):
    """An object or wire message violates the strict protocol."""


class AuthorizationError(WatchdogError):
    """A signature, identity, or role is not authorized."""


class ClosedError(WatchdogError):
    """The watchdog is closed or cannot safely continue."""


class LedgerError(WatchdogError):
    """A durable ledger operation failed or had an ambiguous result."""


class ClockError(WatchdogError):
    """Clock health or deadline checks cannot be trusted."""
