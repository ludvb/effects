"""A lightweight algebraic effects library for Python.

Effect systems provide a powerful way to structure applications by separating
a behavior's intent (an effect) from its implementation (a handler), enabling
runtime behaviors to be composed and modified across different abstraction levels.

Example:

>>> import effects as fx
>>>
>>> # Define an effect type
>>> class Ask(fx.Effect[str]):
...     def __init__(self, question: str):
...         self.question = question
>>>
>>> # Write pure business logic using effects
>>> def greet():
...     name = fx.send(Ask("What's your name?"))
...     return f"Hello, {name}!"
>>>
>>> # Handle effects with different implementations
>>> def handle_ask(effect: Ask) -> str:
...     return "Alice"  # Mock implementation for testing
>>>
>>> with fx.handler(handle_ask, Ask):
...     print(greet())
Hello, Alice!
"""

from .__version__ import __version__
from .effects import (
    Effect,
    NoHandlerError,
    barrier,
    bind,
    describe_effect,
    get_stack,
    handler,
    safe_send,
    send,
)
from .util import stack

__all__ = [
    "Effect",
    "NoHandlerError",
    "__version__",
    "barrier",
    "bind",
    "describe_effect",
    "get_stack",
    "handler",
    "safe_send",
    "send",
    "stack",
]
