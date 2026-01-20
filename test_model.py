from spyruntime import SPyType, SPyValue, i32, spy_object, spy_type, get_type


def test_spy_type_value():
    x = i32(42)
    y = i32(43)
    assert x == i32(42)
    assert x != y
    assert get_type(x) is i32
    assert get_type(i32) is spy_type
