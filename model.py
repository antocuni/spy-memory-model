"""
This file contains functions and types which are supposed to be implemented IN SPY
CODE.

In real world, this would be a .spy file.
"""

from spyruntime import (
    i32,
    w_type,
    blue_generic,
    struct,
    W_Type,
    W_Value,
    gc_box_ptr,
    gc_box_alloc,
    get_type,
    W_GcBoxPtrType,
    is_reference_type,
    gc_box_payload_type,
)


@struct.mut
class GcBase:
    ob_refcnt: i32
    ob_type: w_type


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

# Higher level abstraction for GC-managed pointers built on top of gc_box_ptr and
# gc_box_alloc.


class W_GcPtrType(W_Type):
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
        # check that we got a ptr to the right Box[PAYLOAD]
        BOX_PTR_T = get_type(box_ptr)  # e.g. gc_box_ptr[ObjectObject]
        assert isinstance(BOX_PTR_T, W_GcBoxPtrType)
        T = BOX_PTR_T.TO  # e.g. ObjectObject
        EXPECTED_T = gc_box_payload_type(self.TO)
        assert T is EXPECTED_T
        addr = box_ptr._value
        return W_GcPtrValue(addr, self)


class W_GcPtrValue(W_Value):
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
    return W_GcPtrType(name, T)


@blue_generic
def gc_alloc(T):
    """
    Allocate a GC-managed instance of T, return a gc_ptr[T]
    """

    def impl() -> gc_ptr[T]:
        box_ptr = gc_box_alloc[T]()
        return gc_ptr[T].from_box_ptr(box_ptr)

    return impl


# ======= high level object model ========


@struct
class ObjectObject:
    "Implementation struct for object (empty)"


@struct
class spy_object:
    """
    The root of object hierarchy.

    This is the "dual" of w_object. The relationship is the following:

    - in the interpreter, the "object" type is implemented by w_object

    - the C backend translates this type "model::spy_object" as usual and produces C
      structs and accessor functions

    - the C backend maps w_object to the type "model::spy_object"
    """

    # this is a special syntax: a struct with a single field "__ref__: gc_ptr[...]" is
    # considered to be a reference type
    __ref__: gc_ptr[ObjectObject]

    @staticmethod
    def spy_new():
        "Equivalent for applevel __new__"
        ptr = gc_alloc[spy_object]()
        return spy_object(__ref__=ptr)
