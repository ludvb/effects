"""
Core implementation of the algebraic effects system.

Provides mechanisms to define, send, and handle effects using context managers
and context variables for isolation.
"""

import contextvars
import inspect
import warnings
from functools import wraps
from typing import (
    Callable,
    ContextManager,
    Any,
    TypeVar,
    Generic,
    Type,
    List,
    Tuple,
    Optional,
    ParamSpec,
    overload,
)

from .util import stack


R = TypeVar("R")
E = TypeVar("E", bound="Effect[Any]")
D = TypeVar("D")
T = TypeVar("T")
P = ParamSpec("P")


class Effect(Generic[R]):
    """Base class for all effects."""


class NoHandlerError(Exception):
    """Exception raised when an effect is sent but no handler is found in the current context."""

    __match_args__ = ("effect",)

    def __init__(self, effect: Effect[Any]):
        """Initialize the exception with the unhandled effect."""
        super().__init__(f"No handler for effect: {effect}")
        self.effect = effect


_STACK_VAR: contextvars.ContextVar[
    Optional[List[Tuple[Callable[[Any], Any], Type[Any]]]]
] = contextvars.ContextVar("_STACK_VAR", default=None)
_PTR_VAR: contextvars.ContextVar[Optional[int]] = contextvars.ContextVar(
    "_STACK_PTR_VAR", default=None
)


def get_stack() -> List[Tuple[Callable[[Any], Any], Type[Any]]]:
    current_list = _STACK_VAR.get()
    if current_list is None:
        list_to_set: List[Tuple[Callable[[Any], Any], Type[Any]]] = []
    else:
        # If a list exists (possibly from a copied context), copy it to ensure isolation.
        list_to_set = list(current_list)
    _STACK_VAR.set(list_to_set)
    return list_to_set


class _EffectHandlerContext(Generic[E, R]):
    def __init__(
        self,
        handler_func: Callable[[E], R],
        effect_type: Type[E],
        stack_accessor: Callable[[], List[Tuple[Callable[[Any], Any], Type[Any]]]],
        *,
        on_enter: Optional[Callable[[], None]] = None,
        on_exit: Optional[Callable[[Any, Any, Any], None]] = None,
    ):
        self._handler_func = handler_func
        self._effect_type = effect_type
        self._get_stack = stack_accessor
        self._on_enter = on_enter
        self._on_exit = on_exit

    def __enter__(self):
        stack = self._get_stack()
        stack.append((self._handler_func, self._effect_type))
        if self._on_enter:
            self._on_enter()
        return self._handler_func

    def __exit__(self, exc_type, exc_val, exc_tb):
        stack = self._get_stack()
        expected = (self._handler_func, self._effect_type)
        if stack:
            for i in range(len(stack) - 1, -1, -1):
                if stack[i] == expected:
                    stack.pop(i)
                    if self._on_exit:
                        self._on_exit(exc_type, exc_val, exc_tb)
                    return
            warnings.warn(
                f"Handler {expected} not found on stack during exit.", RuntimeWarning
            )
        else:
            warnings.warn(
                f"Stack empty on exit, but handler {expected} was expected.",
                RuntimeWarning,
            )


def handler(
    handler_func: Callable[[E], R],
    effect_type: Type[E],
    *,
    on_enter: Optional[Callable[[], None]] = None,
    on_exit: Optional[Callable[[Any, Any, Any], None]] = None,
) -> _EffectHandlerContext[E, R]:
    """
    Prepares an effect handler for a specific effect type, to be used in a `with` statement.

    Args:
        handler_func: The function to call when an effect of `effect_type` is sent.
        effect_type: The class of the effect to handle.
        on_enter: Optional function to call when entering the context.
        on_exit: Optional function to call when exiting the context.

    Returns:
        A context manager object (_EffectHandlerContext) that registers the handler.
        The `__enter__` method of this object returns the handler function itself.
    """
    return _EffectHandlerContext(
        handler_func, effect_type, get_stack, on_enter=on_enter, on_exit=on_exit
    )


def send(effect: Effect[R], interpret_final: bool = True) -> R:
    """
    Sends an effect up the handler stack to be processed.

    Args:
        effect: The effect instance to send.
        interpret_final: If True (default), the search for a handler starts from the
                         top-most handler. If False, the search continues from the
                         handler immediately above the one that caught the effect
                         previously within the current handling context. This allows
                         a handler to process an effect and then re-send it (or a
                         different effect) to be caught by handlers further up the stack.

    Returns:
        The result returned by the handler that processed the effect.

    Raises:
        NoHandlerError: If no appropriate handler is found on the stack.
    """
    stack = get_stack()
    ptr = _PTR_VAR.get()
    if interpret_final or ptr is None:
        ptr = len(stack) - 1
    ptr_token = _PTR_VAR.set(ptr)
    try:
        while ptr >= 0:
            handler, eff_type = stack[ptr]
            ptr -= 1
            _PTR_VAR.set(ptr)
            if isinstance(effect, eff_type):
                return handler(effect)
        raise NoHandlerError(effect)
    finally:
        _PTR_VAR.reset(ptr_token)


@overload
def safe_send(
    effect: Effect[R],
    interpret_final: bool = True,
    *,
    default_value: D,
) -> R | D:
    ...

@overload
def safe_send(
    effect: Effect[R],
    interpret_final: bool = True,
) -> R | None:
    ...

def safe_send(
    effect: Effect[R],
    interpret_final: bool = True,
    *,
    default_value: D | None = None,
) -> R | D | None:
    """
    Sends an effect up the handler stack, returning a default value if no handler is found.

    Args:
        effect: The effect instance to send.
        interpret_final: If True (default), the search for a handler starts from the
                         top-most handler. If False, the search continues from the
                         handler immediately above the one that caught the effect
                         previously within the current handling context. This allows
                         a handler to process an effect and then re-send it (or a
                         different effect) to be caught by handlers further up the stack.
        default_value: The value to return if no handler is found for the `effect`.
                       Defaults to `None`.

    Returns:
        The result returned by the handler that processed the effect, or `default_value`
        if no appropriate handler is found on the stack.

    Raises:
        NoHandlerError: If a `NoHandlerError` for a different effect is caught during handling.
    """
    try:
        return send(effect, interpret_final=interpret_final)
    except NoHandlerError as e:
        if e.effect is not effect:
            raise e
        return default_value


def barrier(effect_type: Type[E]):
    """
    Creates a handler that raises NoHandlerError for the specified effect type.

    This is useful for ensuring that certain effects are not handled in specific contexts.

    Args:
        effect_type: The class of the effect to raise an error for.

    Returns:
        A handler function that raises NoHandlerError when called with the specified effect type.
    """

    def _raise(effect):
        raise NoHandlerError(effect)

    return handler(_raise, effect_type)


def bind(
    computation: Callable[P, T],
    *effect_handlers: ContextManager,
    bind_current_context: bool = False,
) -> Callable[P, T]:
    """
    Binds a computation to a list of effect handlers, isolating its effects to
    the provided handlers.

    Args:
        computation: The computation to execute.
        effect_handlers: A list of effect handlers to apply to the computation.
        bind_current_context: If True, include the effect stack of the current
            context in the binding.

    Returns:
        The pure function that executes the computation with the provided effect handlers.
    """
    base_stack = get_stack() if bind_current_context else None
    old_stack = _STACK_VAR.set(base_stack)
    old_stack_ptr = _PTR_VAR.set(None)

    try:
        with stack(*effect_handlers):
            ctx = contextvars.copy_context()
    finally:
        _STACK_VAR.reset(old_stack)
        _PTR_VAR.reset(old_stack_ptr)

    @wraps(computation)
    def _run_generator(*args, **kwargs):
        g = ctx.run(computation, *args, **kwargs)
        while True:
            try:
                yield ctx.run(next, g)
            except StopIteration as e:
                return e.value

    @wraps(computation)
    def _run_function(*args, **kwargs):
        return ctx.run(computation, *args, **kwargs)

    if inspect.isgeneratorfunction(computation):
        return _run_generator
    return _run_function