"""Polling file watcher utilities.

This package exposes a single class, :class:`PollingFileWatcher`, which
compares stat signatures of a configured set of paths to detect creation,
deletion, and modification events.  It is deliberately dependency-free so
it can be dropped into constrained environments.
"""

from .core import PollingFileWatcher, FileEvent

__all__ = ["PollingFileWatcher", "FileEvent"]
