"""Ownership and lifetime in CPython, side by side with C++ smart pointers.

Run: python3 ownership_demo.py
"""

import gc
import sys
import tracemalloc
import weakref
from collections.abc import Callable
from contextlib import ExitStack
from dataclasses import dataclass
from types import TracebackType
from typing import NamedTuple, Self


class Port:
    """Stands in for a handle that must be released: a serial port, a file, a socket."""

    def __init__(self, name: str) -> None:
        self.name = name
        self.closed = False

    def close(self) -> None:
        if not self.closed:
            self.closed = True
            print(f"  close {self.name}")

    def __enter__(self) -> Self:
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        tb: TracebackType | None,
    ) -> None:
        self.close()

    def __del__(self) -> None:
        print(f"  free {self.name}")


print("1. Every name is a shared_ptr: the last reference frees the object at once")
a = Port("A")
b = a  # no copy: a second reference to the same object
print("  after b = a: a is b ->", a is b)
del a
print("  after del a: still alive, closed =", b.closed)
del b  # the count reaches 0 here, and __del__ runs here
print("  after del b: the line above printed first")

print("2. A reference cycle is not freed by counting; weakref breaks it")


class Node:
    def __init__(self, name: str, parent: "Node | None" = None) -> None:
        self.name = name
        self.parent = parent  # strong reference upwards
        self.children: list[Node] = []

    def __del__(self) -> None:
        print(f"  free node {self.name}")


root = Node("root")
child = Node("child", parent=root)  # child -> root
root.children.append(child)  # root -> child: a cycle
del root, child
print("  after del: nothing freed yet")
print("  gc.collect() found", gc.collect(), "unreachable objects")


class WeakNode:
    def __init__(self, name: str, parent: "WeakNode | None" = None) -> None:
        self.name = name
        self._parent = weakref.ref(parent) if parent else None  # like std::weak_ptr
        self.children: list[WeakNode] = []

    @property
    def parent(self) -> "WeakNode | None":
        return self._parent() if self._parent else None  # None once the parent is gone

    def __del__(self) -> None:
        print(f"  free weak node {self.name}")


wroot = WeakNode("root")
wchild = WeakNode("child", parent=wroot)
wroot.children.append(wchild)
print("  parent while alive:", wchild.parent.name if wchild.parent else None)
del wroot
print("  after del wroot, freed by counting alone; child.parent ->", wchild.parent)
del wchild

print("3. RAII: with and ExitStack, including a transfer of ownership")


def open_pair(first: str, second: str, fail_on_second: bool = False) -> ExitStack:
    """Open two ports. On success the caller owns both, as if returned by std::move."""
    with ExitStack() as stack:
        stack.enter_context(Port(first))
        if fail_on_second:
            raise OSError(f"cannot open {second}")
        stack.enter_context(Port(second))
        return stack.pop_all()  # keeps the cleanups alive past the end of this with block


try:
    open_pair("P1", "P2", fail_on_second=True)
except OSError as exc:
    print("  failed:", exc)
with open_pair("Q1", "Q2"):
    print("  both open")
print("  leaving the with block closed both, last opened first")

print("4. Memory per object for 100,000 records of 4 fields")


class Plain:
    def __init__(self, a: int, b: int, c: int, d: int) -> None:
        self.a, self.b, self.c, self.d = a, b, c, d


class Slotted:
    __slots__ = ("a", "b", "c", "d")

    def __init__(self, a: int, b: int, c: int, d: int) -> None:
        self.a, self.b, self.c, self.d = a, b, c, d


@dataclass(slots=True)
class DataSlots:
    a: int
    b: int
    c: int
    d: int


class Named(NamedTuple):
    a: int
    b: int
    c: int
    d: int


def plain_tuple(a: int, b: int, c: int, d: int) -> tuple[int, int, int, int]:
    return (a, b, c, d)


def bytes_per_object(make: Callable[[int, int, int, int], object], n: int = 100_000) -> float:
    """Bytes allocated per object, counting the 8-byte slot in the list that holds it."""
    gc.collect()
    tracemalloc.start()
    before = tracemalloc.get_traced_memory()[0]
    objs = [make(1, 2, 3, 4) for _ in range(n)]  # small ints are shared objects
    after = tracemalloc.get_traced_memory()[0]
    tracemalloc.stop()
    del objs
    return (after - before) / n


print(f"  {'':24s}{'bytes':>6s}  tracked by the GC: new, after gc.collect()")
for label, cls in [
    ("ordinary class", Plain),
    ("class with __slots__", Slotted),
    ("dataclass(slots=True)", DataSlots),
    ("NamedTuple", Named),
    ("plain tuple", plain_tuple),
]:
    sample = cls(1, 2, 3, 4)  # keep one alive to ask the collector about it
    fresh = gc.is_tracked(sample)
    gc.collect()
    print(
        f"  {label:24s}{bytes_per_object(cls):6.0f}  {fresh!s:>5s}, {gc.is_tracked(sample)!s:>5s}"
    )
print("  Python", sys.version.split()[0])
