"""
This file contains functions and types which are supposed to be implemented IN SPY
CODE.

In real world, this would be a .spy file.
"""

from spyruntime import (
    i32,
    spy_type,
    blue_generic,
    struct,
    SPyType,
    SPyValue,
    gc_box_ptr,
    gc_box_alloc,
    get_type,
    GcBoxPtrType,
)


@struct.mut
class GcBase:
    ob_refcnt: i32
    ob_type: spy_type


@blue_generic
def Box(T):
    ## assert not is_reference_type(T)

    @struct.mut
    class _Box:
        base: GcBase
        payload: T

    name = f"Box[{T.name}]"
    _Box.name = name
    return _Box


# ======= gc_ptr[T] and gc_alloc[T] ========

# Higher level abstraction for GC-managed pointers built on top of gc_box_ptr and
# gc_box_alloc.


class GcPtrType(SPyType):
    """
    Thin wrapper around box_ptr[T].

    In SPy it would be something like this:

    @blue.generic(T)
    def gc_ptr(T):

        @struct
        class _gc_ptr:
            _box_ptr: gc_box_ptr[T]

           @blue
           def __getattr__(...): ...

           @blue
           def __setattr__(...): ...

        return _gc_ptr
    """

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
    """
    Allocate a GC-managed instance of T, return a gc_ptr[T]
    """

    def impl() -> gc_ptr[T]:
        box_ptr = gc_box_alloc[T]()
        return gc_ptr[T].from_box_ptr(box_ptr)

    return impl
