from __future__ import annotations


class TRClientError(Exception):
    """Base exception for TR client errors."""


class TRSessionExpiredError(TRClientError):
    """Raised when the TR session has expired and requires re-authentication."""


class TRConnectionError(TRClientError):
    """Raised when the TR WebSocket connection fails."""
