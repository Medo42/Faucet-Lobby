# dict-like class with automatic expiration of entries.

from ordereddict import OrderedDict
from time import time

class expirationset:
    def __init__(self, retention_secs, callback=None):
        self._retention_secs = retention_secs
        self._data = OrderedDict()
        self._callback = callback

    def add(self, key):
        self.cleanup_stale()
        if(key in self._data):
            del self._data[key]
        self._data[key] = time()

    def discard(self, key):
        if(key in self._data):
            del self._data[key]
            if(self._callback is not None):
                self._callback(key, False)

    def __contains__(self, key):
        self.cleanup_stale()
        return key in self._data

    def cleanup_stale(self):
        curtime = time()
        while(True):
            try:
                key, regtime = self._data.iteritems().next()
            except StopIteration:
                break

            if(curtime-regtime < self._retention_secs):
                break
            
            del self._data[key]
            if(self._callback is not None):
                self._callback(key, True)
