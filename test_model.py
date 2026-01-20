from spyruntime import SPyType, SPyValue, i32, spy_object, spy_type, get_type, struct
from model import Box

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
    assert get_type(i32) is spy_type


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


def test_Box():
    BT = Box[i32]
    assert BT.name == "Box[i32]"
    assert repr(BT) == "<spy type Box[i32]>"
    assert list(BT.fields.keys()) == ["base", "payload"]
    BT2 = Box[i32]
    assert BT is BT2
