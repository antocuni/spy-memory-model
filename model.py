"""
This file contains functions and types which are supposed to be implemented IN SPY
CODE.

In real world, this would be a .spy file.
"""

from spyruntime import (
    i32,
    u8,
    w_type,
    blue_generic,
    struct,
    W_Type,
    W_Value,
    get_type,
    Box,
    gc_ptr,
    gc_alloc,
    gc_alloc_varsize,
    W_GcPtrValue,
    ObjectObject,
)


# ======= high level object model ========


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

    # convention to denote reference types
    __ref__: gc_ptr[ObjectObject]

    @staticmethod
    def spy_new():
        "Equivalent for applevel __new__"
        ptr = gc_alloc[ObjectObject, spy_object]()
        return spy_object(__ref__=ptr)


@struct
class StringObject:
    base: ObjectObject
    length: i32
    utf8: u8[...]


@struct
class spy_str:
    __ref__: gc_ptr[StringObject]

    @staticmethod
    def spy_new():
        "Equivalent for applevel __new__"
        # allocate StringObject with 5 bytes for "test\0"
        ptr = gc_alloc_varsize[StringObject, spy_str](5)
        ptr.length = i32(4)
        ptr.utf8[0] = u8(ord("t"))
        ptr.utf8[1] = u8(ord("e"))
        ptr.utf8[2] = u8(ord("s"))
        ptr.utf8[3] = u8(ord("t"))
        ptr.utf8[4] = u8(ord("\0"))
        return spy_str(__ref__=ptr)

    def _as_py_str(self) -> str:
        "Convert to Python string for testing"
        ptr = self.__ref__
        length = ptr.length._value
        chars = []
        for i in range(length):
            byte_val = ptr.utf8[i]
            if byte_val is not None:
                chars.append(chr(byte_val._value))
        return "".join(chars)
