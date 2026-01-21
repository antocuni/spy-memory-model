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



def is_reference_type(T: W_Type) -> bool:
    # Check if T is a reference type (has a single __ref__ field of type gc_ptr)
    # We need to check this carefully to avoid circular imports
    return (
        T.is_struct()
        and list(T.fields) == ["__ref__"]
        and hasattr(T.fields["__ref__"], "TO")  # gc_ptr has a TO attribute
        and T.fields["__ref__"].name.startswith("gc_ptr[")
    )


def gc_ptr_payload_type(T):
    """
    Return the payload type for a gc_ptr[T].
    For reference types, returns the TO of the __ref__ field.
    For other types, returns T itself.
    """
    if is_reference_type(T):
        return T.fields["__ref__"].TO
    else:
        return T


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


# ======= gc_ptr[T] and gc_alloc[T] ========


class W_GcPtrType(W_Type):
    """
    Pointer to a GC-managed instance of T.
    Internally stores the address of a Box[PAYLOAD] where PAYLOAD is computed
    based on whether T is a reference type or not.
    """

    def __init__(self, name, TO):
        super().__init__(name)
        self.TO = TO

    def __call__(self, addr):
        return W_GcPtrValue(addr, self)


class W_GcPtrValue(W_Value):
    @property
    def addr(self):
        return self._value

    @property
    def gc_base(self):
        """Access the GC base (refcount and type) of the allocated object"""
        T = self._spy_type.TO
        PAYLOAD = gc_ptr_payload_type(T)
        BOX_T = Box[PAYLOAD]
        box = MEMORY.load(self.addr, BOX_T)
        return box.base

    def __getattr__(self, attr):
        # Load the box from memory and access the payload
        T = self._spy_type.TO
        PAYLOAD = gc_ptr_payload_type(T)
        BOX_T = Box[PAYLOAD]
        box = MEMORY.load(self.addr, BOX_T)
        return getattr(box.payload, attr)

    def __setattr__(self, attr, value):
        if attr in ("_value", "_spy_type"):
            super().__setattr__(attr, value)
        else:
            # Load the box from memory and set on the payload
            T = self._spy_type.TO
            PAYLOAD = gc_ptr_payload_type(T)
            BOX_T = Box[PAYLOAD]
            box = MEMORY.load(self.addr, BOX_T)
            setattr(box.payload, attr, value)


@blue_generic
def gc_ptr(T):
    """
    gc_ptr[T]: pointer to a GC-managed T
    """
    name = f"gc_ptr[{T.name}]"
    return W_GcPtrType(name, T)


@blue_generic
def gc_alloc(T):
    """
    Allocate a GC-managed instance of T, return a gc_ptr[T].
    This implicitly allocates a Box[PAYLOAD] where PAYLOAD depends on T.
    """

    def impl() -> gc_ptr[T]:
        if T.is_box():
            raise TypeError(f"Cannot allocate a Box type: {T.name}")

        PAYLOAD = gc_ptr_payload_type(T)
        BOX_T = Box[PAYLOAD]

        addr = MEMORY.alloc(BOX_T)
        ptr = gc_ptr[T](addr)
        ptr.gc_base.ob_refcnt = i32(1)
        ptr.gc_base.ob_type = T
        return ptr

    return impl
