import types
from typing import TYPE_CHECKING, Any, Iterable, TypeVar, Union, cast, get_args, get_origin

if TYPE_CHECKING:  # pragma: no cover - type check only
    from .effects import Effect


_TYPEVAR_TYPE = type(TypeVar("T"))
_UNION_ORIGIN = types.UnionType
_TYPING_UNION = Union


def normalize_effect_annotations(
    effect_type: Any | tuple[Any, ...], *, effect_base: type["Effect[Any]"]
) -> tuple[Any, ...]:
    if isinstance(effect_type, tuple):
        raw: Iterable[Any] = effect_type
    else:
        raw = (effect_type,)

    normalized: list[Any] = []
    for candidate in raw:
        origin = get_origin(candidate)
        if origin is _UNION_ORIGIN or origin is _TYPING_UNION:
            normalized.extend(
                normalize_effect_annotations(get_args(candidate), effect_base=effect_base)
            )
            continue

        effect_cls = effect_class_from_annotation(candidate, effect_base=effect_base)
        if origin is None or not get_args(candidate):
            normalized.append(effect_cls)
        else:
            normalized.append(candidate)

    return tuple(normalized)


def format_annotation(annotation: Any, *, effect_base: type["Effect[Any]"]) -> str:
    effect_cls = effect_class_from_annotation(annotation, effect_base=effect_base)
    args = get_args(annotation)
    if not args:
        return effect_cls.__name__
    arg_names = ", ".join(_format_type_name(arg) for arg in args)
    return f"{effect_cls.__name__}[{arg_names}]"


def annotation_matches_effect(
    effect: "Effect[Any]", annotation: Any, *, effect_base: type["Effect[Any]"]
) -> bool:
    effect_cls = effect_class_from_annotation(annotation, effect_base=effect_base)
    if not isinstance(effect, effect_cls):
        return False

    expected_args = get_args(annotation)
    if not expected_args:
        return True

    inferred = infer_effect_type_args(effect, effect_cls, len(expected_args))
    if inferred is None:
        return bool(not _class_has_typevar_annotations(effect_cls))

    return all(
        _type_arg_matches(expected, actual)
        for expected, actual in zip(expected_args, inferred, strict=False)
    )


def describe_effect(effect: "Effect[Any]", *, effect_base: type["Effect[Any]"]) -> str:
    effect_cls = effect.__class__
    stored = getattr(effect, "__effect_type_args__", None)
    if isinstance(stored, tuple) and stored:
        args = ", ".join(_format_type_name(arg) for arg in stored)
        return f"{effect_cls.__name__}[{args}]"

    params_raw = getattr(effect_cls, "__parameters__", ())
    params = tuple(params_raw) or tuple(getattr(effect_cls, "__type_params__", ()))
    if params:
        inferred = infer_effect_type_args(effect, effect_cls, len(params))
        if inferred:
            args = ", ".join(_format_type_name(arg) for arg in inferred)
            return f"{effect_cls.__name__}[{args}]"

    return repr(effect)


def effect_class_from_annotation(
    annotation: Any, *, effect_base: type["Effect[Any]"]
) -> type["Effect[Any]"]:
    origin = get_origin(annotation)
    effect_cls = origin if origin is not None else annotation
    if not (isinstance(effect_cls, type) and issubclass(effect_cls, effect_base)):
        raise TypeError(f"Effect handler must target Effect subclasses, got {effect_cls!r}.")
    return cast(type["Effect[Any]"], effect_cls)


def infer_effect_type_args(
    effect: "Effect[Any]",
    effect_cls: type["Effect[Any]"],
    expected_len: int,
) -> tuple[type[Any], ...] | None:
    """Infers the concrete type arguments of a generic effect instance."""
    # This function serves as the main entry point for type argument inference.
    # It first checks for pre-computed type arguments cached on the effect
    # instance (`__effect_type_args__`). If the cache is present and valid, it
    # is returned immediately. If the cache is not present, it falls back to
    # inferring the types by inspecting the instance's attributes and their
    # values via `_infer_effect_type_args_from_instance`. This fallback ensures
    # the system works correctly for effects that were not created as
    # dataclasses or did not use the caching mechanism.

    # No type arguments case
    if expected_len == 0:
        return ()

    # Fast path: Check for cached type arguments on the instance.
    stored_args = getattr(effect, "__effect_type_args__", None)
    if isinstance(stored_args, tuple) and len(stored_args) == expected_len:
        return stored_args  # type: ignore[return-value]

    # Fallback: If no cache is found, perform inference by inspecting the
    # instance's values.
    return infer_effect_type_args_from_instance(effect, effect_cls, expected_len)


def infer_effect_type_args_from_instance(
    effect: "Effect[Any]",
    effect_cls: type["Effect[Any]"],
    expected_len: int,
) -> tuple[type[Any], ...] | None:
    params_raw = getattr(effect_cls, "__parameters__", ())
    params = cast(tuple[Any, ...], tuple(params_raw))
    if not params:
        params = cast(tuple[Any, ...], tuple(getattr(effect_cls, "__type_params__", ())))
    if not params:
        return None

    annotations = getattr(effect_cls, "__annotations__", {})
    bindings: dict[Any, type[Any]] = {}
    for name, annotation in annotations.items():
        if not hasattr(effect, name):
            continue
        value = getattr(effect, name)
        _collect_typevar_bindings(annotation, value, bindings)

    resolved: list[type[Any] | None] = []
    for param in params[:expected_len]:
        resolved.append(bindings.get(param))

    if any(arg is None for arg in resolved):
        return None

    return tuple(resolved)  # type: ignore[return-value]


def _collect_typevar_bindings(annotation: Any, value: Any, bindings: dict[Any, type[Any]]) -> None:
    if isinstance(annotation, _TYPEVAR_TYPE):
        bindings.setdefault(annotation, type(value))
        return

    origin = get_origin(annotation)
    if origin is _UNION_ORIGIN or origin is _TYPING_UNION:
        for option in get_args(annotation):
            _collect_typevar_bindings(option, value, bindings)
        return

    if origin is None:
        return

    args = get_args(annotation)

    # Import Callable here to avoid circular dependency
    from collections.abc import Callable as CallableABC

    match origin:
        case _ if origin is CallableABC:
            # Handle Callable types - extract parameter types from function annotations
            if not callable(value):
                return
            if not args or len(args) != 2:
                return
            param_types, return_type = args

            # Try to get function annotations
            if hasattr(value, "__annotations__"):
                annotations = value.__annotations__
                # Get parameter types from the function's annotations
                param_names = [k for k in annotations if k != "return"]

                if isinstance(param_types, (list, tuple)) and param_names:
                    # Match TypeVars in parameter types with actual function parameter types
                    for param_annotation, param_name in zip(param_types, param_names, strict=False):
                        if param_name in annotations:
                            actual_type = annotations[param_name]
                            if isinstance(param_annotation, _TYPEVAR_TYPE):
                                bindings.setdefault(param_annotation, actual_type)
                            else:
                                _collect_typevar_bindings(param_annotation, actual_type, bindings)

            # Handle return type if it contains TypeVars
            if (
                isinstance(return_type, _TYPEVAR_TYPE)
                and hasattr(value, "__annotations__")
                and "return" in value.__annotations__
            ):
                bindings.setdefault(return_type, value.__annotations__["return"])
            return

        case _ if origin is tuple:
            if not isinstance(value, tuple):
                return
            if not args:
                return
            if len(args) == 2 and args[1] is Ellipsis:
                element_annotation = args[0]
                for item in value:
                    _collect_typevar_bindings(element_annotation, item, bindings)
                return
            if len(args) != len(value):
                return
            for annotation_part, item in zip(args, value, strict=False):
                _collect_typevar_bindings(annotation_part, item, bindings)
            return

        case _ if origin in {list, set, frozenset}:
            if not isinstance(value, origin):
                return
            if not args:
                return
            try:
                iterator = iter(value)
            except TypeError:
                return
            try:
                first_item = next(iterator)
            except StopIteration:
                return
            _collect_typevar_bindings(args[0], first_item, bindings)
            return

        case _ if origin is dict:
            if not isinstance(value, dict):
                return
            if len(args) != 2:
                return
            if not value:
                return
            key, mapped_value = next(iter(value.items()))
            key_annotation, value_annotation = args
            _collect_typevar_bindings(key_annotation, key, bindings)
            _collect_typevar_bindings(value_annotation, mapped_value, bindings)
            return

        case _:
            return


def _class_has_typevar_annotations(effect_cls: type["Effect[Any]"]) -> bool:
    annotations = getattr(effect_cls, "__annotations__", {})
    return any(_annotation_contains_typevar(annotation) for annotation in annotations.values())


def _annotation_contains_typevar(annotation: Any) -> bool:
    if isinstance(annotation, _TYPEVAR_TYPE):
        return True
    origin = get_origin(annotation)
    if origin is _UNION_ORIGIN or origin is _TYPING_UNION:
        return any(_annotation_contains_typevar(arg) for arg in get_args(annotation))
    if origin is None:
        return False
    return any(_annotation_contains_typevar(arg) for arg in get_args(annotation))


def _type_arg_matches(expected: Any, actual: type[Any]) -> bool:
    if expected is Any:
        return True
    if actual is None:
        return False

    origin = get_origin(expected)
    if origin is _UNION_ORIGIN or origin is _TYPING_UNION:
        return any(_type_arg_matches(opt, actual) for opt in get_args(expected))

    if isinstance(expected, _TYPEVAR_TYPE):
        return True

    if isinstance(expected, type):
        try:
            return issubclass(actual, expected)
        except TypeError:
            return False

    return expected == actual


def _format_type_name(tp: Any) -> str:
    if tp is Any:
        return "Any"
    if isinstance(tp, type):
        return tp.__name__
    return getattr(tp, "__name__", repr(tp))
