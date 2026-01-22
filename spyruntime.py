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
        if not isinstance(key, tuple):
            key = (key,)
        if key not in self.cache:
            self.cache[key] = self.func(*key)
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

    def is_vararray(self) -> bool:
        return False

    def __call__(self, value):
        """Allow instantiation: SPy_I32(42) returns W_Value"""
        return W_Value(value, self)

    def __getitem__(self, size):
        """Allow array syntax: i32[10] or i32[...]"""
        if size is ...:
            return W_VarArrayType(self)
        else:
            raise NotImplementedError("Fixed-size arrays not yet supported")

    def __repr__(self):
        return f"<spy type {self.name}>"


class W_VarArrayType(W_Type):
    """Variable-sized array type, e.g., u8[...]"""

    def __init__(self, item_type: W_Type):
        self.item_type = item_type
        name = f"{item_type.name}[...]"
        super().__init__(name)

    def is_vararray(self) -> bool:
        return True


class W_VarArrayValue:
    """
    Wrapper for variable array access.
    Supports indexing: arr[0], arr[1], etc.
    """

    def __init__(self, items: list, item_type: W_Type):
        self.items = items
        self.item_type = item_type

    def __getitem__(self, index: int):
        return self.items[index]

    def __setitem__(self, index: int, value):
        self.items[index] = value

    def __len__(self):
        return len(self.items)


# Built-in types
w_i32 = W_Type("i32")
w_u8 = W_Type("u8")
w_object = W_Type("object")
w_type = W_Type("type")

i32 = w_i32  # just for convenience of typing
u8 = w_u8  # just for convenience of typing


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
        self.vararray_field = None  # name of the flexible array member, if any

    def is_struct(self) -> bool:
        return True

    def has_vararray(self) -> bool:
        return self.vararray_field is not None

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
            val = self._value[attr]
            # Check if this is a vararray field
            if self._spy_type.vararray_field == attr:
                field_type = self._spy_type.fields[attr]
                assert isinstance(field_type, W_VarArrayType)
                # Return a wrapper that supports indexing
                return W_VarArrayValue(val, field_type.item_type)
            return val
        # Check if it's a method on the struct type
        if hasattr(self._spy_type, attr):
            method = getattr(self._spy_type, attr)
            if callable(method):
                # Bind the method to this instance
                from functools import partial
                return partial(method, self)
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
    vararray_field = None
    assert hasattr(cls, "__annotations__")
    field_list = list(cls.__annotations__.items())
    for idx, (field_name, field_type) in enumerate(field_list):
        assert isinstance(field_type, W_Type)
        if field_type.is_vararray():
            # flexible array member must be the last field
            assert idx == len(field_list) - 1, \
                f"Flexible array member {field_name} must be the last field"
            assert vararray_field is None, "Only one flexible array member allowed"
            vararray_field = field_name
        fields[field_name] = field_type

    struct_type = W_StructType(cls.__name__, fields)
    struct_type.vararray_field = vararray_field

    # Copy all methods from the class to the struct type
    for name in dir(cls):
        if not name.startswith('__'):
            attr = getattr(cls, name)
            if callable(attr):
                setattr(struct_type, name, attr)

    return struct_type


# in real spy, we have mutable and immutable structs. Here, everything is mutable as we
# don't have a real need to enfore immutability.
struct.mut = struct


# ======= typed heap simulation =====


@struct.mut
class GcHeader:
    ob_refcnt: i32
    ob_type: w_type


@blue_generic
def Box(T):
    if T.is_struct():
        assert "__ref__" not in T.fields

    @struct.mut
    class _Box:
        gc_header: GcHeader
        payload: T

    name = f"Box[{T.name}]"
    _Box.name = name
    return _Box


class Memory:
    def __init__(self):
        self.mem = {0: "NULL"}

    def alloc(self, T):
        # we can allocate only GC-managed memory in this simulation
        assert T.is_box()
        addr = max(self.mem) + 100
        self.mem[addr] = T(gc_header=GcHeader())  # uninitialized
        return addr

    def load(self, addr, expected_T):
        v = self.mem[addr]
        assert get_type(v) is expected_T
        return v


MEMORY = Memory()


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
    def gc_header(self):
        """Access the GC base (refcount and type) of the allocated object"""
        T = self._spy_type.TO
        BOX_T = Box[T]
        box = MEMORY.load(self.addr, BOX_T)
        return box.gc_header

    def __getattr__(self, attr):
        # gc_ptr[T] always points to Box[T], access the payload
        T = self._spy_type.TO
        BOX_T = Box[T]
        box = MEMORY.load(self.addr, BOX_T)
        return getattr(box.payload, attr)

    def __setattr__(self, attr, value):
        if attr in ("_value", "_spy_type"):
            super().__setattr__(attr, value)
        else:
            # gc_ptr[T] always points to Box[T], set on the payload
            T = self._spy_type.TO
            BOX_T = Box[T]
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
def gc_alloc(LLTYPE, HLTYPE=None):
    """
    Allocate a GC-managed object.

    - LLTYPE must be a value type and it's the payload.

    - HLTYPE is the type that it's stored in gc_header.ob_type, and it's what is
      returned by get_type().

    We support two kinds of invocation:

    - gc_alloc[T]: in this case, the dynamic type is equal to the payload type. E.g. if
      you have a `@struct Point`, you can gc_alloc[Point]().

    - gc_alloc[T, V] if you want to customize the dynamic type. The main use case is to
      allocate reference types, e.g. gc_alloc[ObjectObject, spy_object].

    Under the hood, it allocates a Box[T], which contains the needed GC header, but this
    is transparent to the user.

    In both cases, it returns gc_ptr[T].
    """
    if LLTYPE.is_box():
        raise TypeError(f"Cannot allocate a Box type: {LLTYPE.name}")

    if HLTYPE is None:
        HLTYPE = LLTYPE
    else:
        assert HLTYPE.fields == {"__ref__": gc_ptr[LLTYPE]}

    def impl() -> gc_ptr[LLTYPE]:
        BOX_T = Box[LLTYPE]
        addr = MEMORY.alloc(BOX_T)
        ptr = gc_ptr[LLTYPE](addr)
        ptr.gc_header.ob_refcnt = i32(1)
        ptr.gc_header.ob_type = HLTYPE
        return ptr

    return impl


@blue_generic
def gc_alloc_varsize(LLTYPE, HLTYPE=None):
    """
    Allocate a GC-managed object with a variable-sized array member.

    Similar to gc_alloc, but the struct must have a flexible array member.
    Returns a function that takes the array count as parameter.

    Usage:
        ptr = gc_alloc_varsize[StringData](5)  # allocates StringData with 5 array items
    """
    if LLTYPE.is_box():
        raise TypeError(f"Cannot allocate a Box type: {LLTYPE.name}")

    if not LLTYPE.is_struct():
        raise TypeError(f"{LLTYPE.name} must be a struct with flexible array member")

    if not LLTYPE.has_vararray():
        raise TypeError(f"{LLTYPE.name} does not have a flexible array member")

    if HLTYPE is None:
        HLTYPE = LLTYPE
    else:
        assert HLTYPE.fields == {"__ref__": gc_ptr[LLTYPE]}

    def alloc_with_count(count: int) -> gc_ptr[LLTYPE]:
        BOX_T = Box[LLTYPE]
        addr = MEMORY.alloc(BOX_T)
        ptr = gc_ptr[LLTYPE](addr)
        ptr.gc_header.ob_refcnt = i32(1)
        ptr.gc_header.ob_type = HLTYPE

        # Store the array count in a special attribute
        # Initialize the variable array
        vararray_field = LLTYPE.vararray_field
        vararray_type = LLTYPE.fields[vararray_field]
        assert vararray_type.is_vararray()

        # Create a list to hold the array items
        box = MEMORY.load(addr, BOX_T)
        # Store array as a list in the vararray field
        box.payload._value[vararray_field] = [None] * count
        box.payload._value["__vararray_count__"] = count

        return ptr

    return alloc_with_count
