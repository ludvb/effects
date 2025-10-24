import dataclasses as dc

import effects as fx


def test_generic_dispatch():
    @dc.dataclass
    class GenericEffect[T](fx.Effect[T]):
        value: T

    @fx.handler
    def specialized_handler(e: GenericEffect[str]) -> str:
        return str(e.value)

    with specialized_handler:
        result = fx.send(GenericEffect("test"))
        assert result == "test"
        try:
            fx.send(GenericEffect(123))
            assert False
        except fx.NoHandlerError:
            pass


def test_generic_dispatch_multiargs():
    @dc.dataclass
    class GenericEffect[T1, T2](fx.Effect[T1]):
        value1: T1
        value2: T2

    @fx.handler
    def specialized_handler(e: GenericEffect[str, int]):
        return e.value1

    with specialized_handler:
        result = fx.send(GenericEffect("test", 123))
        assert result == "test"
        try:
            result = fx.send(GenericEffect("test", "123"))
            assert False
        except fx.NoHandlerError:
            pass
        try:
            fx.send(GenericEffect(123, 123))
            assert False
        except fx.NoHandlerError:
            pass


def test_generic_dispatch_tuple_payload():
    @dc.dataclass
    class TupleEffect[T](fx.Effect[T]):
        value: tuple[T, ...]

    @fx.handler
    def specialized_handler(e: TupleEffect[str]) -> str:
        return "|".join(e.value)

    with specialized_handler:
        result = fx.send(TupleEffect(("a", "b")))
        assert result == "a|b"
        try:
            fx.send(TupleEffect((1, 2)))
            assert False
        except fx.NoHandlerError:
            pass


def test_generic_dispatch_list_payload():
    @dc.dataclass
    class ListEffect[T](fx.Effect[T]):
        value: list[T]

    @fx.handler
    def specialized_handler(e: ListEffect[str]) -> int:
        return len(e.value)

    with specialized_handler:
        result = fx.send(ListEffect(["a", "b"]))
        assert result == 2
        try:
            fx.send(ListEffect([1, 2]))
            assert False
        except fx.NoHandlerError:
            pass
        try:
            fx.send(ListEffect([]))
            assert False
        except fx.NoHandlerError:
            pass


def test_generic_dispatch_dict_payload():
    @dc.dataclass
    class DictEffect[K, V](fx.Effect[V]):
        data: dict[K, V]

    @fx.handler
    def specialized_handler(e: DictEffect[str, int]) -> int:
        return sum(e.data.values())

    with specialized_handler:
        result = fx.send(DictEffect({"a": 1, "b": 2}))
        assert result == 3
        try:
            fx.send(DictEffect({"a": "1"}))
            assert False
        except fx.NoHandlerError:
            pass
        try:
            fx.send(DictEffect({}))
            assert False
        except fx.NoHandlerError:
            pass


def test_no_handler_error_mentions_type_arguments():
    @dc.dataclass
    class GenericEffect[T](fx.Effect[T]):
        value: T

    try:
        fx.send(GenericEffect(123))
        assert False
    except fx.NoHandlerError as exc:
        assert "GenericEffect[int]" in str(exc)
