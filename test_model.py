import pytest

from spyruntime import (
    i32,
    u8,
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


def test_spy_type_value():
    x = i32(1)
    y = i32(2)
    assert x == i32(1)
    assert x != y
    assert get_type(x) is i32
    assert get_type(i32) is w_type


def test_struct():
    @struct
    class Point:
        x: i32
        y: i32

    p = Point(x=i32(1), y=i32(2))
    assert p.x == i32(1)
    assert p.y == i32(2)
    #
    # uninitialized struct, will be used by gc_alloc
    p = Point()
    assert p._value == {"x": None, "y": None}
    assert p.x is None
    assert p.y is None
    p.x = i32(3)
    p.y = i32(4)
    assert p.x == i32(3)
    assert p.y == i32(4)
    assert p._value == {"x": i32(3), "y": i32(4)}


def test_nested_struct():
    @struct
    class Point:
        x: i32
        y: i32

    @struct
    class Rect:
        a: Point
        b: Point

    r = Rect(a=Point(x=i32(1), y=i32(2)), b=Point(x=i32(3), y=i32(4)))
    assert r.a.x == i32(1)
    assert r.a.y == i32(2)
    assert r.b.x == i32(3)
    assert r.b.y == i32(4)

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

    # we can access the GC header and ob_type through .base
    assert ptr.base.gc_header.ob_refcnt == i32(1)
    assert ptr.base.ob_type is Point

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
    assert get_type(box.payload) is ObjectObject

    # the dynamic type is spy_object
    assert box.base.ob_type is spy_object
    assert get_type(obj) is spy_object

    # We can access the GC header and ob_type through the gc_ptr's .base
    assert ptr_obj.base.gc_header.ob_refcnt == i32(1)
    assert ptr_obj.base.ob_type is spy_object


def test_gc_alloc_box_error():
    # Attempting to allocate a Box type should raise an error
    with pytest.raises(TypeError, match="Cannot allocate a Box type"):
        gc_alloc[Box[i32]]()


def test_gc_alloc_varsize():
    from spyruntime import gc_alloc_varsize, u8

    @struct
    class StringData:
        length: i32
        chars: u8[...]  # flexible array member

    # alloc StringData + 5 extra items of chars
    ptr = gc_alloc_varsize[StringData](5)

    # verify the type
    assert get_type(ptr) is gc_ptr[StringData]

    # verify we can access regular fields
    ptr.length = i32(4)
    assert ptr.length == i32(4)

    # verify we can access and modify the variable array
    ptr.chars[0] = u8(ord("t"))
    ptr.chars[1] = u8(ord("e"))
    ptr.chars[2] = u8(ord("s"))
    ptr.chars[3] = u8(ord("t"))
    ptr.chars[4] = u8(ord("\0"))

    # verify we can read back the values
    assert ptr.chars[0] == u8(ord("t"))
    assert ptr.chars[1] == u8(ord("e"))
    assert ptr.chars[2] == u8(ord("s"))
    assert ptr.chars[3] == u8(ord("t"))
    assert ptr.chars[4] == u8(ord("\0"))

    # verify the array has the right length
    assert len(ptr.chars) == 5


def test_spy_str():
    from model import spy_str, StringObject

    # create a spy_str using spy_new
    s = spy_str.spy_new()

    # verify the type
    assert get_type(s) is spy_str

    # verify the internal pointer points to StringObject
    ptr = s.__ref__
    assert get_type(ptr) is gc_ptr[StringObject]

    # verify the ob_type is set correctly
    assert ptr.base.ob_type is spy_str

    # verify we can access the fields
    assert ptr.length == i32(4)
    assert ptr.utf8[0] == u8(ord("t"))
    assert ptr.utf8[1] == u8(ord("e"))
    assert ptr.utf8[2] == u8(ord("s"))
    assert ptr.utf8[3] == u8(ord("t"))
    assert ptr.utf8[4] == u8(ord("\0"))

    # verify _as_py_str works
    assert s._as_py_str() == "test"
