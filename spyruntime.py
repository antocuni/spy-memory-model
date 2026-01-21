"""
This file contains functions and types which are supposed to be implemented by the
SPy runtime
"""

from dataclasses import dataclass
from typing import Callable, Any
import itertools


class blue_generic:
    """
    Like spy's @blue.generic decorator
    """

    def __init__(self, func: Callable):
        self.func = func
        self.cache = {}

    def __getitem__(self, key: Any):
        """Allow square bracket syntax: fn[x]"""
        if key not in self.cache:
            self.cache[key] = self.func(key)
        return self.cache[key]

    def __repr__(self):
        return f"<@blue_generic {self.func.__name__}>"


class W_Value:
    """A value with an associated SPy type"""

    def __init__(self, value: Any, spy_type: "W_Type"):
        self._value = value
        self._spy_type = spy_type

    def __repr__(self):
        return f"<spy value {self._value}: {self._spy_type.name}>"

    def __eq__(self, other):
        if isinstance(other, W_Value):
            return self._value == other._value and self._spy_type == other._spy_type
        return NotImplemented


class W_Type:
    def __init__(self, name: str):
        self.name = name

    def is_struct(self) -> bool:
        return False

    def is_box(self) -> bool:
        return self.name.startswith("Box[")

    def __call__(self, value):
        """Allow instantiation: SPy_I32(42) returns W_Value"""
        return W_Value(value, self)

    def __repr__(self):
        return f"<spy type {self.name}>"


# Built-in types
w_i32 = W_Type("i32")
w_u8 = W_Type("u8")
w_object = W_Type("object")
w_type = W_Type("type")

i32 = w_i32  # just for convenience of typing


def get_type(x):
    """
    Moral equivalent to vm.dynamic_type
    """
    if isinstance(x, W_Type):
        return w_type
    elif isinstance(x, W_Value):
        return x._spy_type
    else:
        raise TypeError


class W_StructType(W_Type):
    def __init__(self, name: str, fields: dict[str, W_Type]) -> None:
        super().__init__(name)
        self.fields = fields

    def is_struct(self) -> bool:
        return True

    def __call__(self, **kwargs):
        for key in kwargs:
            if key not in self.fields:
                raise TypeError(f"unexpected argument: {key}")
        d = kwargs.copy()
        for attr in self.fields:
            if attr not in d:
                T = self.fields[attr]
                if T.is_struct():
                    d[attr] = T()  # uninitialized
                else:
                    d[attr] = None  # uninitialized
        return W_StructValue(d, self)


class W_StructValue(W_Value):
    def __getattr__(self, attr):
        if attr in self._value:
            return self._value[attr]
        raise AttributeError(attr)

    def __setattr__(self, attr, value):
        if attr in ("_spy_type", "_value"):
            super().__setattr__(attr, value)
        elif attr in self._spy_type.fields:
            self._value[attr] = value
        else:
            raise AttributeError(value)


def struct(cls=None):
    """
    @struct decorator
    """

    fields = {}
    assert hasattr(cls, "__annotations__")
    for field_name, field_type in cls.__annotations__.items():
        assert isinstance(field_type, W_Type)
        fields[field_name] = field_type

    struct_type = W_StructType(cls.__name__, fields)

    # hack hack hack
    if hasattr(cls, "spy_new"):
        struct_type.spy_new = cls.spy_new

    return struct_type


# in real spy, we have mutable and immutable structs. Here, everything is mutable as we
# don't have a real need to enfore immutability.
struct.mut = struct


# ======= typeded heap simulation =====


@struct.mut
class GcBase:
    ob_refcnt: i32
    ob_type: w_type


class Memory:
    def __init__(self):
        self.mem = {0: "NULL"}

    def alloc(self, T):
        # we can allocate only GC-managed memory in this simulation
        assert T.is_box()
        addr = max(self.mem) + 100
        self.mem[addr] = T(base=GcBase())  # uninitialized
        return addr

    def load(self, addr, expected_T):
        v = self.mem[addr]
        assert get_type(v) is expected_T
        return v


MEMORY = Memory()

# ======= gc_box_ptr[T] and gc_box_alloc[T] ========


class W_GcBoxPtrType(W_Type):
    def __init__(self, name, TO):
        super().__init__(name)
        self.TO = TO

    def __call__(self, addr):
        return W_GcBoxPtrValue(addr, self)


class W_GcBoxPtrValue(W_Value):
    @property
    def addr(self):
        return self._value

    def __getattr__(self, attr):
        # we expect to have a Box[T] at address "addr"
        BOX_PTR_T = self._spy_type  # gc_box_ptr[T]
        T = BOX_PTR_T.TO
        BOX_T = Box[T]
        box = MEMORY.load(self.addr, BOX_T)

        # now we can read the attribute from the box
        return getattr(box, attr)


@blue_generic
def gc_box_ptr(T):
    """
    gc_box_ptr[T]: pointer to a GC-managed Box[T]
    """
    name = f"gc_box_ptr[{T.name}]"
    return W_GcBoxPtrType(name, T)


@blue_generic
def gc_box_alloc(T):
    """
    Allocate a GC-managed Box[T] and return a gc_box_ptr[T]
    """
    # this is the magic which makes is possible to call gc_alloc[str] and get a
    # Box[StringObject] with ob_type==str
    PAYLOAD = gc_box_payload_type(T)
    BOX = Box[PAYLOAD]

    def impl() -> gc_box_ptr[PAYLOAD]:
        addr = MEMORY.alloc(BOX)
        box_ptr = gc_box_ptr[PAYLOAD](addr)
        box_ptr.base.ob_refcnt = i32(1)
        box_ptr.base.ob_type = T
        return box_ptr

    return impl


def gc_box_payload_type(T):
    """
    XXX explain me better
    """
    if is_reference_type(T):
        # __ref__ is a gc_ptr[PAYLOAD]
        return T.fields["__ref__"].TO
    else:
        return T


def is_reference_type(T: W_Type) -> bool:
    from model import W_GcPtrType

    return (
        T.is_struct()
        and list(T.fields) == ["__ref__"]
        and isinstance(T.fields["__ref__"], W_GcPtrType)
    )


@blue_generic
def Box(T):
    assert not is_reference_type(T)

    @struct.mut
    class _Box:
        base: GcBase
        payload: T

    name = f"Box[{T.name}]"
    _Box.name = name
    return _Box
