"""
This file contains functions and types which are supposed to be implemented IN SPY
CODE.

In real world, this would be a .spy file.
"""

from spyruntime import i32, spy_type, blue_generic, struct


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
