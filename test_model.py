import pytest

from spyruntime import (
    W_Value,
    i32,
    w_type,
    get_type,
    struct,
    MEMORY,
    Box,
    gc_ptr,
    gc_alloc,
    W_GcPtrValue,
)
from model import spy_object, ObjectObject

# prebuilt values to be used in tests, just to make typing easier
v0 = i32(0)
v1 = i32(1)
v2 = i32(2)
v3 = i32(3)
v4 = i32(4)


def test_spy_type_value():
    x = v1
    y = v2
    assert x == i32(1)
    assert x != y
    assert get_type(x) is i32
    assert get_type(i32) is w_type


def test_struct():
    @struct
    class Point:
        x: i32
        y: i32

    p = Point(x=v1, y=v2)
    assert p.x == v1
    assert p.y == v2
    #
    # uninitialized struct, will be used by gc_alloc
    p = Point()
    assert p._value == {"x": None, "y": None}
    assert p.x is None
    assert p.y is None
    p.x = v3
    p.y = v4
    assert p.x == v3
    assert p.y == v4
    assert p._value == {"x": v3, "y": v4}


def test_nested_struct():
    @struct
    class Point:
        x: i32
        y: i32

    @struct
    class Rect:
        a: Point
        b: Point

    r = Rect(a=Point(x=v1, y=v2), b=Point(x=v3, y=v4))
    assert r.a.x == v1
    assert r.a.y == v2
    assert r.b.x == v3
    assert r.b.y == v4

    # uninitialized
    r = Rect()
    assert r.a.x is None
    assert r.a.y is None
    assert r.b.x is None
    assert r.b.y is None


def test_Box():
    BT = Box[i32]
    assert BT.name == "Box[i32]"
    assert repr(BT) == "<spy type Box[i32]>"
    assert list(BT.fields.keys()) == ["gc_header", "payload"]
    assert BT.is_box()
    BT2 = Box[i32]
    assert BT is BT2


def test_gc_alloc():
    @struct
    class Point:
        x: i32
        y: i32

    ptr = gc_alloc[Point]()

    # ptr has type gc_ptr[Point]
    assert get_type(ptr) is gc_ptr[Point]

    # ptr points to a **Box[Point]** in memory
    box = MEMORY.mem[ptr.addr]
    assert get_type(box) is Box[Point]

    # we can access the GC base
    assert ptr.gc_header.ob_refcnt == i32(1)
    assert ptr.gc_header.ob_type is Point

    # we can read/write attributes OF THE PAYLOAD
    ptr.x = i32(1)
    ptr.y = i32(2)
    assert ptr.x == i32(1)
    assert ptr.y == i32(2)

    # writing to the payload writes to the box
    assert box.payload.x == i32(1)
    assert box.payload.y == i32(2)


def test_spy_object():
    # instantiate an object, and check that we actually allocated a Box[ObjectObject]
    obj = spy_object.spy_new()
    ptr_obj = obj.__ref__

    assert isinstance(ptr_obj, W_GcPtrValue)
    # gc_alloc[ObjectObject, spy_object] returns gc_ptr[ObjectObject]
    assert get_type(ptr_obj) is gc_ptr[ObjectObject]

    # The gc_ptr[ObjectObject] points to a Box[ObjectObject] in memory
    box = MEMORY.mem[ptr_obj.addr]
    assert get_type(box) is Box[ObjectObject]
    assert box.gc_header.ob_type is spy_object
    assert get_type(box.payload) is ObjectObject

    # We can access the GC base through the gc_ptr
    assert ptr_obj.gc_header.ob_refcnt == i32(1)
    assert ptr_obj.gc_header.ob_type is spy_object


def test_gc_alloc_box_error():
    # Attempting to allocate a Box type should raise an error
    with pytest.raises(TypeError, match="Cannot allocate a Box type"):
        gc_alloc[Box[i32]]()
