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
    get_type,
    Box,
    gc_ptr,
    gc_alloc,
    W_GcPtrValue,
)


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
        ptr = gc_alloc[ObjectObject, spy_object]()
        return spy_object(__ref__=ptr)
