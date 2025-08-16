import contextvars
import inspect
import warnings
from collections.abc import Callable, Generator
from functools import wraps
from types import TracebackType
from typing import (
    Any,
    ContextManager,
    ParamSpec,
    TypeVar,
    overload,
)

from .util import stack

R = TypeVar("R")  # Return type for effects
E = TypeVar("E", bound="Effect[Any]")  # Effect type (must be subclass of Effect)
D = TypeVar("D")  # Default value type for safe_send
T = TypeVar("T")  # Generic type variable for function returns
P = ParamSpec("P")  # Function parameters specification
G = TypeVar("G")  # Generator yield type


class Effect[R]:
    """Base class for all effects."""


class NoHandlerError(Exception):
    """Exception raised when an effect is sent but no handler is found in the current context."""

    __match_args__ = ("effect",)

    def __init__(self, effect: Effect[Any]):
        """Initialize the exception with the unhandled effect."""
        super().__init__(f"No handler for effect: {effect}")
        self.effect = effect


class _EffectHandler[E, R]:
    """Effect handler that acts as a context manager for stack management."""

    def __init__(
        self,
        handler_func: Callable[[E], R],
        effect_type: type[E],
        stack_accessor: Callable[[], list["_EffectHandler[Any, Any]"]],
        *,
        on_enter: Callable[[], None] | None = None,
        on_exit: Callable[[Any, Any, Any], None] | None = None,
    ):
        self._handler_func = handler_func
        self._effect_type = effect_type
        self._get_stack = stack_accessor
        self._on_enter = on_enter
        self._on_exit = on_exit

    def __enter__(self):
        """Register the handler on the stack when entering the context."""
        stack = self._get_stack()
        stack.append(self)
        if self._on_enter:
            self._on_enter()
        return self._handler_func

    def __repr__(self) -> str:
        """Return a string representation of the handler for debugging."""
        func_name = getattr(self._handler_func, "__name__", repr(self._handler_func))
        type_name = self._effect_type.__name__
        return f"_EffectHandler({func_name}, {type_name})"

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc_val: BaseException | None,
        exc_tb: TracebackType | None,
    ) -> None:
        """Remove the handler from the stack when exiting the context."""
        stack = self._get_stack()
        if stack:
            for i in range(len(stack) - 1, -1, -1):
                if stack[i] is self:
                    stack.pop(i)
                    if self._on_exit:
                        self._on_exit(exc_type, exc_val, exc_tb)
                    return
            warnings.warn(f"Handler {self} not found on stack during exit.", RuntimeWarning)
        else:
            warnings.warn(
                f"Stack empty on exit, but handler {self} was expected.",
                RuntimeWarning,
            )


_STACK_VAR: contextvars.ContextVar[list["_EffectHandler[Any, Any]"] | None] = (
    contextvars.ContextVar("_STACK_VAR", default=None)
)
_PTR_VAR: contextvars.ContextVar[int | None] = contextvars.ContextVar(
    "_STACK_PTR_VAR", default=None
)


def get_stack() -> list["_EffectHandler[Any, Any]"]:
    """Get the current effect handler stack, creating one if it doesn't exist.

    Returns a list of _EffectHandler instances currently on the stack.
    The handlers are ordered from bottom (first added) to top (most recent).

    This function is useful for:
    - Inspecting the current handler configuration
    - Manually manipulating handler order with bind()
    - Debugging effect resolution

    Example:
        >>> @handler
        >>> def my_handler(e: MyEffect) -> str:
        ...     return "handled"
        >>>
        >>> with my_handler:
        ...     stack = get_stack()
        ...     print(stack)  # [_EffectHandler(my_handler, MyEffect)]
    """
    current_list = _STACK_VAR.get()
    if current_list is None:
        list_to_set: list[_EffectHandler[Any, Any]] = []
    else:
        # If a list exists (possibly from a copied context), copy it to ensure isolation.
        list_to_set = list(current_list)
    _STACK_VAR.set(list_to_set)
    return list_to_set


@overload
def handler(
    handler_func: Callable[[E], R],
    effect_type: type[E],
    *,
    on_enter: Callable[[], None] | None = None,
    on_exit: Callable[[Any, Any, Any], None] | None = None,
) -> _EffectHandler[E, R]: ...


@overload
def handler(
    handler_func: Callable[[E], R],
    *,
    on_enter: Callable[[], None] | None = None,
    on_exit: Callable[[Any, Any, Any], None] | None = None,
) -> _EffectHandler[E, R]: ...


def handler(
    handler_func: Callable[[E], R],
    effect_type: type[E] | None = None,
    *,
    on_enter: Callable[[], None] | None = None,
    on_exit: Callable[[Any, Any, Any], None] | None = None,
) -> _EffectHandler[E, R]:
    """Prepare an effect handler for a specific effect type, to be used in a `with` statement.

    Args:
        handler_func: The function to call when an effect is sent. The effect type can be
                      inferred from the type annotation of the first parameter.
        effect_type: The class of the effect to handle. If not provided, it will be inferred
                     from the type annotation of handler_func's first parameter.
        on_enter: Optional function to call when entering the context.
        on_exit: Optional function to call when exiting the context.

    Returns:
        A context manager object (_EffectHandlerContext) that registers the handler.
        The `__enter__` method of this object returns the handler function itself.

    Raises:
        TypeError: If effect_type is not provided and cannot be inferred from handler_func.
    """
    if effect_type is None:
        # Try to infer the effect type from the handler function's type annotations
        sig = inspect.signature(handler_func)
        params = list(sig.parameters.values())

        if not params:
            raise TypeError(
                "Cannot infer effect type: handler_func has no parameters. "
                "Please provide effect_type explicitly."
            )

        first_param = params[0]
        param_annotation = first_param.annotation

        if param_annotation is inspect.Parameter.empty:
            raise TypeError(
                f"Cannot infer effect type: parameter '{first_param.name}' has no type annotation. "
                "Please provide effect_type explicitly or add a type annotation."
            )

        # Handle both direct type and generic type annotations
        # For example: Query or Effect[str] or subclasses
        if hasattr(param_annotation, "__origin__"):
            # It's a generic type, get the origin
            effect_type = param_annotation.__origin__
        else:
            # It's a direct type
            effect_type = param_annotation

        # Verify it's actually an Effect subclass
        if not (isinstance(effect_type, type) and issubclass(effect_type, Effect)):
            raise TypeError(
                f"Inferred type {effect_type} is not a subclass of Effect. "
                "Please provide effect_type explicitly."
            )

    return _EffectHandler(handler_func, effect_type, get_stack, on_enter=on_enter, on_exit=on_exit)


def send(effect: Effect[R], interpret_final: bool = True) -> R:
    """Send an effect up the handler stack to be processed.

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
            handler_obj = stack[ptr]
            ptr -= 1
            _PTR_VAR.set(ptr)
            if isinstance(effect, handler_obj._effect_type):
                return handler_obj._handler_func(effect)
        raise NoHandlerError(effect)
    finally:
        _PTR_VAR.reset(ptr_token)


@overload
def safe_send(
    effect: Effect[R],
    interpret_final: bool = True,
    *,
    default_value: D,
) -> R | D: ...


@overload
def safe_send(
    effect: Effect[R],
    interpret_final: bool = True,
) -> R | None: ...


def safe_send(
    effect: Effect[R],
    interpret_final: bool = True,
    *,
    default_value: D | None = None,
) -> R | D | None:
    """Send an effect up the handler stack, returning a default value if no handler is found.

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


def barrier(effect_type: type[E]):
    """Create a handler that raises NoHandlerError for the specified effect type.

    This is useful for ensuring that certain effects are not handled in specific contexts.

    Args:
        effect_type: The class of the effect to raise an error for.

    Returns:
        A handler function that raises NoHandlerError when called with the specified effect type.
    """

    def _raise(effect: E) -> None:
        raise NoHandlerError(effect)

    return handler(_raise, effect_type)


@overload
def bind(
    computation: Callable[P, Generator[G, Any, R]],
    *effect_handlers: ContextManager[Any],
    bind_current_context: bool = False,
) -> Callable[P, Generator[G, Any, R]]: ...


@overload
def bind(
    computation: Callable[P, T],
    *effect_handlers: ContextManager[Any],
    bind_current_context: bool = False,
) -> Callable[P, T]: ...


def bind(
    computation: Callable[P, Any],
    *effect_handlers: ContextManager[Any],
    bind_current_context: bool = False,
) -> Callable[P, Any]:
    """Bind a computation to effect handlers, isolating its effects to the provided handlers.

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
    def _run_generator(*args: P.args, **kwargs: P.kwargs) -> Generator[Any, Any, Any]:
        g = ctx.run(computation, *args, **kwargs)
        while True:
            try:
                yield ctx.run(next, g)
            except StopIteration as e:
                return e.value

    @wraps(computation)
    def _run_function(*args: P.args, **kwargs: P.kwargs) -> Any:
        return ctx.run(computation, *args, **kwargs)

    if inspect.isgeneratorfunction(computation):
        return _run_generator
    return _run_function
