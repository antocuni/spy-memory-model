from spyruntime import (
    W_Value,
    i32,
    w_object,
    w_type,
    get_type,
    struct,
    gc_box_alloc,
    gc_box_ptr,
    MEMORY,
)
from model import Box, gc_ptr, gc_alloc

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
    assert list(BT.fields.keys()) == ["base", "payload"]
    assert BT.is_box()
    BT2 = Box[i32]
    assert BT is BT2


def test_gc_box_alloc():
    ptr_box = gc_box_alloc[i32]()

    # we stored a Box[i32] in memory
    assert get_type(MEMORY.mem[ptr_box.addr]) is Box[i32]

    # the static type is gc_box_ptr[i32]
    assert get_type(ptr_box) is gc_box_ptr[i32]

    # the type stored in the gc header is i32
    assert ptr_box.base.ob_refcnt == i32(1)
    assert ptr_box.base.ob_type is i32

    # the payload is uninitialized
    assert ptr_box.payload is None


def test_gc_alloc():
    @struct
    class Point:
        x: i32
        y: i32

    ptr = gc_alloc[Point]()

    # ptr points to a **Box[Point]** in memory
    box = MEMORY.mem[ptr.addr]
    assert get_type(box) is Box[Point]

    # we can read/write attributes OF THE PAYLOAD
    ptr.x = i32(1)
    ptr.y = i32(2)
    assert ptr.x == i32(1)
    assert ptr.y == i32(2)

    # writing to the payload writes to the box
    assert box.payload.x == i32(1)
    assert box.payload.y == i32(2)
