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


class SPyValue:
    """A value with an associated SPy type"""

    def __init__(self, value: Any, spy_type: "SPyType"):
        self._value = value
        self._spy_type = spy_type

    def __repr__(self):
        return f"<spy value {self._value}: {self._spy_type.name}>"

    def __eq__(self, other):
        if isinstance(other, SPyValue):
            return self._value == other._value and self._spy_type == other._spy_type
        return NotImplemented


class SPyType:
    def __init__(self, name: str):
        self.name = name

    def is_struct(self) -> bool:
        return False

    def is_box(self) -> bool:
        return self.name.startswith("Box[")

    def __call__(self, value):
        """Allow instantiation: SPy_I32(42) returns SPyValue"""
        return SPyValue(value, self)

    def __repr__(self):
        return f"<spy type {self.name}>"


# Built-in types
i32 = SPyType("i32")
u8 = SPyType("u8")
spy_object = SPyType("object")
spy_type = SPyType("type")


def get_type(x):
    """
    Moral equivalent to vm.dynamic_type
    """
    if isinstance(x, SPyType):
        return spy_type
    elif isinstance(x, SPyValue):
        return x._spy_type
    else:
        raise TypeError


class SPyStructType(SPyType):
    def __init__(self, name: str, fields: dict[str, SPyType]) -> None:
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
        return SPyStructValue(d, self)


class SPyStructValue(SPyValue):
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
        assert isinstance(field_type, SPyType)
        fields[field_name] = field_type

    struct_type = SPyStructType(cls.__name__, fields)
    return struct_type


# in real spy, we have mutable and immutable structs. Here, everything is mutable as we
# don't have a real need to enfore immutability.
struct.mut = struct


# ======= typeded heap simulation =====


class Memory:
    def __init__(self):
        self.mem = {0: "NULL"}

    def alloc(self, T):
        from model import GcBase

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


class GcBoxPtrType(SPyType):
    def __init__(self, name, TO):
        super().__init__(name)
        self.TO = TO

    def __call__(self, addr):
        return GcBoxPtrValue(addr, self)


class GcBoxPtrValue(SPyValue):
    @property
    def addr(self):
        return self._value

    def __getattr__(self, attr):
        from model import Box

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
    return GcBoxPtrType(name, T)


@blue_generic
def gc_box_alloc(T):
    """
    Allocate a GC-managed Box[T] and return a gc_box_ptr[T]
    """
    from model import Box

    ## # this is the magic which makes is possible to call gc_alloc[str] and get a
    ## # Box[StringObject] with ob_type==str
    ## if is_reference_type(T):
    ##     # __ref__ is a gc_ptr[PAYLOAD]
    ##     PAYLOAD = T.fields["__ref__"].TO
    ## else:
    ##     PAYLOAD = T
    PAYLOAD = T
    BOX = Box[PAYLOAD]

    def impl() -> gc_box_ptr[PAYLOAD]:
        addr = MEMORY.alloc(BOX)
        box_ptr = gc_box_ptr[PAYLOAD](addr)
        box_ptr.base.ob_refcnt = i32(1)
        box_ptr.base.ob_type = T
        return box_ptr

    return impl


# ======= gc_ptr[T] and gc_alloc[T] ========


class GcPtrType(SPyType):
    def __init__(self, name, TO):
        super().__init__(name)
        self.TO = TO

    def __call__(self, addr):
        raise TypeError("Cannot create {self.name} directly: use .from_box_ptr")

    def from_box_ptr(self, box_ptr: "gc_box_ptr[T]") -> "gc_ptr[T]":
        # check that we got a ptr to the right Box[T]
        BOX_PTR_T = get_type(box_ptr)
        assert isinstance(BOX_PTR_T, GcBoxPtrType)
        assert BOX_PTR_T.TO is self.TO
        addr = box_ptr._value
        return GcPtrValue(addr, self)


class GcPtrValue(SPyValue):
    @property
    def addr(self):
        return self._value

    def as_box_ptr(self) -> "gc_box_ptr[T]":
        T = self._spy_type.TO
        return gc_box_ptr[T](self.addr)

    def __getattr__(self, attr):
        # reading from gc_ptr[T] is equivalent to read from gc_box_ptr[T].payload
        box_ptr = self.as_box_ptr()
        return getattr(box_ptr.payload, attr)

    def __setattr__(self, attr, value):
        if attr in ("_value", "_spy_type"):
            super().__setattr__(attr, value)
        else:
            # writing to gc_ptr[T] is equivalent to write to gc_box_ptr[T].payload
            box_ptr = self.as_box_ptr()
            setattr(box_ptr.payload, attr, value)


@blue_generic
def gc_ptr(T):
    """
    gc_ptr[T]: pointer to a GC-managed T
    """
    name = f"gc_ptr[{T.name}]"
    return GcPtrType(name, T)


@blue_generic
def gc_alloc(T):
    def impl() -> gc_ptr[T]:
        box_ptr = gc_box_alloc[T]()
        return gc_ptr[T].from_box_ptr(box_ptr)

    return impl
