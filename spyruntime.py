"""
This file contains functions and types which are supposed to be implemented by the
SPy runtime
"""

from dataclasses import dataclass
from typing import Callable, Any
import itertools


class blue_generic:
    """
    Like spy's @blue.generic decorator
    """

    def __init__(self, func: Callable):
        self.func = func
        self.cache = {}

    def __getitem__(self, key: Any):
        """Allow square bracket syntax: fn[x]"""
        if key not in self.cache:
            self.cache[key] = self.func(key)
        return self.cache[key]

    def __repr__(self):
        return f"<@blue_generic {self.func.__name__}>"


class SPyValue:
    """A value with an associated SPy type"""

    def __init__(self, value: Any, spy_type: "SPyType"):
        self._value = value
        self._spy_type = spy_type

    def __repr__(self):
        return f"<spy value {self._value}: {self._spy_type.name}>"

    def __eq__(self, other):
        if isinstance(other, SPyValue):
            return self._value == other._value and self._spy_type == other._spy_type
        return NotImplemented


class SPyType:
    def __init__(self, name: str):
        self.name = name

    def is_struct(self) -> bool:
        return False

    def __call__(self, value):
        """Allow instantiation: SPy_I32(42) returns SPyValue"""
        return SPyValue(value, self)

    def __repr__(self):
        return f"<spy type {self.name}>"


# Built-in types
i32 = SPyType("i32")
u8 = SPyType("u8")
spy_object = SPyType("object")
spy_type = SPyType("type")


def get_type(x):
    """
    Moral equivalent to vm.dynamic_type
    """
    if isinstance(x, SPyType):
        return spy_type
    elif isinstance(x, SPyValue):
        return x._spy_type
    else:
        raise TypeError


class SPyStructType(SPyType):
    def __init__(self, name: str, fields: dict[str, SPyType]) -> None:
        super().__init__(name)
        self.fields = fields

    def is_struct(self) -> bool:
        return True

    def __call__(self, **kwargs):
        for key in kwargs:
            if key not in self.fields:
                raise TypeError(f"unexpected argument: {key}")
        d = kwargs.copy()
        for attr in self.fields:
            if attr not in d:
                d[attr] = None  # uninitialized
        return SPyStructValue(d, self)


class SPyStructValue(SPyValue):
    def __getattr__(self, attr):
        if attr in self._value:
            return self._value[attr]
        raise AttributeError(attr)


def struct(cls=None):
    """
    @struct decorator
    """

    fields = {}
    assert hasattr(cls, "__annotations__")
    for field_name, field_type in cls.__annotations__.items():
        assert isinstance(field_type, SPyType)
        fields[field_name] = field_type

    struct_type = SPyStructType(cls.__name__, fields)
    return struct_type
