"""Local-only watchdog primitives; Azure use requires separate feasibility approval."""

from .errors import AuthorizationError, ClosedError, ProtocolError

__all__ = ["AuthorizationError", "ClosedError", "ProtocolError"]
