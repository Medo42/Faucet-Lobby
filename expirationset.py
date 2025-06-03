"""Lightweight set that automatically expires entries after a timeout."""

from __future__ import annotations

from collections import OrderedDict
from time import time
from typing import Callable, Dict, Iterator, Optional

class expirationset:
    """Set-like container which expires items after ``retention_secs`` seconds."""

    def __init__(self, retention_secs: int, callback: Optional[Callable[[object, bool], None]] = None) -> None:
        self._retention_secs = retention_secs
        self._data: Dict[object, float] = OrderedDict()
        self._callback = callback

    def add(self, key: object) -> None:
        self.cleanup_stale()
        if(key in self._data):
            del self._data[key]
        self._data[key] = time()

    def discard(self, key: object) -> None:
        if(key in self._data):
            del self._data[key]
            if(self._callback is not None):
                self._callback(key, False)

    def __contains__(self, key: object) -> bool:
        self.cleanup_stale()
        return key in self._data

    def cleanup_stale(self) -> None:
        curtime = time()
        while(True):
            try:
                key, regtime = next(iter(self._data.items()))
            except StopIteration:
                break

            if(curtime-regtime < self._retention_secs):
                break
            
            del self._data[key]
            if(self._callback is not None):
                self._callback(key, True)
