from spyruntime import SPyType, SPyValue, i32, spy_object, spy_type, get_type, struct


def test_spy_type_value():
    x = i32(42)
    y = i32(43)
    assert x == i32(42)
    assert x != y
    assert get_type(x) is i32
    assert get_type(i32) is spy_type


def test_struct():
    @struct
    class Point:
        x: i32
        y: i32

    x = i32(1)
    y = i32(2)
    p = Point(x=x, y=y)
    assert p.x == x
    assert p.y == y
    #
    # uninitialized struct, will be used by gc_alloc
    p = Point()
    assert p.x is None
    assert p.y is None
