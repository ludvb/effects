"""Effects library main module, exposing core components."""

from .__version__ import __version__
from .effects import (
    Effect,
    NoHandlerError,
    barrier,
    bind,
    handler,
    safe_send,
    send,
)
from .util import stack

__all__ = [
    "__version__",
    "Effect",
    "handler",
    "safe_send",
    "send",
    "NoHandlerError",
    "stack",
    "barrier",
    "bind",
]