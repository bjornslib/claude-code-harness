"""Graceful shutdown handling for the code generation pipeline.

Registers OS signal handlers so that a long-running generation loop
can be interrupted cleanly, writing a checkpoint before exiting.
"""

from __future__ import annotations

import logging
import signal
import types
from typing import Callable

logger = logging.getLogger(__name__)


class GracefulShutdownHandler:
    """Register SIGINT / SIGTERM handlers to request graceful shutdown.

    Use as a context manager around the main generation loop:

    .. code-block:: python

        with GracefulShutdownHandler() as handler:
            for node in nodes:
                handler.check_shutdown()
                process(node)

    When a signal is received the ``shutdown_requested`` flag is set.
    The main loop should call :meth:`check_shutdown` between iterations
    to detect the request.

    Args:
        checkpoint_fn: Optional callback invoked on shutdown to persist
            the current generation state.
    """

    def __init__(
        self,
        checkpoint_fn: Callable[[], None] | None = None,
    ) -> None:
        self._shutdown_requested = False
        self._checkpoint_fn = checkpoint_fn
        self._original_sigint: signal.Handlers | None = None
        self._original_sigterm: signal.Handlers | None = None

    @property
    def shutdown_requested(self) -> bool:
        """Return ``True`` if a shutdown signal has been received."""
        return self._shutdown_requested

    def check_shutdown(self) -> None:
        """Check for a pending shutdown request.

        Raises:
            SystemExit: If shutdown has been requested. A checkpoint is
                written (if configured) before the exit.
        """
        if self._shutdown_requested:
            logger.info("Graceful shutdown initiated")
            if self._checkpoint_fn is not None:
                logger.info("Writing checkpoint before exit")
                self._checkpoint_fn()
            raise SystemExit(0)

    # ------------------------------------------------------------------
    # Signal handling
    # ------------------------------------------------------------------

    def _handle_signal(
        self,
        signum: int,
        frame: types.FrameType | None,
    ) -> None:
        """Set the shutdown flag when SIGINT or SIGTERM is received."""
        sig_name = signal.Signals(signum).name
        logger.warning("Received %s — requesting graceful shutdown", sig_name)
        self._shutdown_requested = True

    # ------------------------------------------------------------------
    # Context manager
    # ------------------------------------------------------------------

    def __enter__(self) -> GracefulShutdownHandler:
        """Install signal handlers."""
        self._original_sigint = signal.getsignal(signal.SIGINT)
        self._original_sigterm = signal.getsignal(signal.SIGTERM)
        signal.signal(signal.SIGINT, self._handle_signal)
        signal.signal(signal.SIGTERM, self._handle_signal)
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc_val: BaseException | None,
        exc_tb: types.TracebackType | None,
    ) -> None:
        """Restore original signal handlers."""
        if self._original_sigint is not None:
            signal.signal(signal.SIGINT, self._original_sigint)
        if self._original_sigterm is not None:
            signal.signal(signal.SIGTERM, self._original_sigterm)
