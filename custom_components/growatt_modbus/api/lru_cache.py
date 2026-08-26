"""A small fixed-size LRU cache.

A general-purpose container rather than anything Modbus-specific, which is
why it no longer lives in utils.py. Used to memoise the register-sequence
plan for a set of keys (see device.py), where the same key set recurs on
every poll.
"""

from __future__ import annotations

from collections import OrderedDict
from collections.abc import Iterator, MutableMapping


class LRUCache[K, V](MutableMapping):
    """
    A least-recently used (LRU) cache with a fixed cache size.

    This class acts as a dictionary but has a limited size. If the number of
    entries in the cache exeeds the cache size, the leat-recently accessed
    entry will be discareded.

    This is implemented using an ``OrderedDict``. On every access the accessed
    entry is moved to the front by re-inserting it into the ``OrderedDict``.
    When adding an entry and the cache size is exceeded, the last entry will
    be discareded.
    """

    def __init__(self, capacity=None):
        self.capacity = capacity
        self.cache: OrderedDict[K, V] = OrderedDict()

    @property
    def lru(self) -> list[K]:
        return list(self.cache.keys())

    @property
    def length(self) -> int:
        return len(self.cache)

    def clear(self) -> None:
        self.cache.clear()

    def __len__(self) -> int:
        return self.length

    def __contains__(self, key: object) -> bool:
        return key in self.cache

    def __setitem__(self, key: K, value: V) -> None:
        self.set(key, value)

    def __delitem__(self, key: K) -> None:
        del self.cache[key]

    def __getitem__(self, key) -> V:
        value = self.get(key)
        if value is None:
            raise KeyError(key)

        return value

    def __iter__(self) -> Iterator[K]:
        return iter(self.cache)

    def get[D](self, key: K, default: D | None = None) -> V | D | None:
        value = self.cache.get(key)

        if value is not None:
            # Move the entry to the front by re-inserting it
            del self.cache[key]
            self.cache[key] = value

            return value

        return default

    def set(self, key: K, value: V):
        if self.cache.get(key):
            # Move the entry to the front by re-inserting it
            del self.cache[key]
            self.cache[key] = value
        else:
            self.cache[key] = value

            # Check, if the cache is full and we have to remove old items
            # If the queue is of unlimited size, self.capacity is NaN and
            # x > NaN is always False in Python and the cache won't be cleared.
            if self.capacity is not None and self.length > self.capacity:
                self.cache.popitem(last=False)
