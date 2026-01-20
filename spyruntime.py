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
        self.value = value
        self.spy_type = spy_type

    def __repr__(self):
        return f"<spy value {self.value}: {self.spy_type.name}>"

    def __eq__(self, other):
        if isinstance(other, SPyValue):
            return self.value == other.value and self.spy_type == other.spy_type
        return self.value == other


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
        return x.spy_type
    else:
        raise TypeError
