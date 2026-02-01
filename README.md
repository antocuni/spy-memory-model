# SPy memory model simulation

Playground for experimenting with different design of memory models for SPy.

- `spyruntime.py`: this represent the core functionality offered by the SPy interpreter:
  builtin types, `@blue_generic` decorator, a simulation of the heap, etc.

- `model.py`: this is code which in real world will be implemented in `*.spy` files


Moreover, `PLAN.spy` contains a pseudocode version of them, probably easier to follow.

# High level plan

We want to support multiple GC strategies, including:

  - SPy-only refcounting

  - CPython-based refcounting: all GC-managed objects are subclasses of `PyObject`

  - [whippet](https://github.com/wingo/whippet)

  - [bdwgc](https://github.com/bdwgc/bdwgc) ("Boehm GC")

To achieve that, we have a customizable `GcHeader` struct which changes depending on the
GC strategy. In the example it contains the `refcnt` field.

We also have an `ObjectObject` struct, which is root of the object hierarchy and must be
the base of all GC-managed objects. It contains a pointer to the type, and the among the
other things the type must have a "visitor" function which knows how to visit all its
children. It will be used by the GCs in various ways:

  - tracing GCs will use it to trace all the children

  - refcounting GCs will use it to DECREF all the children upon destruction

Finally, we have a `spy_object` struct which is just a thin wrapper around
`gc_ptr[ObjectObject]`; structs with a single `__ref__: gc_ptr[T]` fields are called
**reference types**.

A **boxed struct** is one whose first field is `ObjectObject`.  `Box[T]` creates a box
wrapper if needed. `Box[T] is T` if T is already boxed.

`gc_alloc[T]` allocates a `Box[T]` and returns a `gc_ptr[T]`.

`gc_alloc` also supports a second form: `gc_alloc[T, HLTYPE]`: allocates a `Box[T]`, but
sets the `ob_type` field to `HLTYPE`. This is needed because to allocate high-level
types, e.g.:

```
ps: gc_ptr[StringObject] = gc_alloc[StringObject, spy_str]
```

In this case, we allocate a `StringObject`, but we want `ob_type` to report `spy_str`.

`get_dynamic_type(obj)` returns `obj.base.ob_type`
