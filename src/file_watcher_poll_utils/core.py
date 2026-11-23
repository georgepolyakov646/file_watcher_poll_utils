"""Core polling watcher implementation.

The watcher stores a stat signature for every path it is told to observe.
On each call to :meth:`PollingFileWatcher.poll`, it re-stats the configured
paths and compares the results with the previous signature.  A path that
did not exist before but exists now produces a ``created`` event; the
reverse produces a ``deleted`` event; a path whose signature changed but
still exists produces a ``modified`` event.

Signature choice
----------------
We use ``os.stat_result.st_mtime_ns`` and ``st_size`` as the signature.
``st_mtime_ns`` is available on all platforms Python supports and has
nanosecond resolution where the filesystem provides it, which is enough to
distinguish rapid successive writes in tests without sleeping.  We do not
use ``st_ino`` because Windows does not populate it meaningfully, and we do
not hash file contents because that would defeat the point of a cheap poll.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from enum import Enum
from typing import Dict, Iterable, List, Optional, Tuple


class FileEventType(Enum):
    """The kind of change detected for a path."""

    CREATED = "created"
    MODIFIED = "modified"
    DELETED = "deleted"


@dataclass(frozen=True)
class FileEvent:
    """A single change observed for a path.

    ``signature`` is the new signature for created/modified events and
    ``None`` for deleted events, because there is nothing left to stat.
    """

    path: str
    event_type: FileEventType
    signature: Optional[Tuple[int, int]]


class PollingFileWatcher:
    """Poll a fixed set of paths for creation, modification, and deletion.

    The set of paths is fixed at construction time.  This is a deliberate
    simplification: a polling watcher that can grow its watch list needs a
    way to distinguish "newly watched" from "newly created", and the
    simplest honest rule is to only report events for paths the caller
    explicitly asked about.

    Parameters
    ----------
    paths:
        Iterable of filesystem paths to observe.  Duplicates are collapsed.
    """

    def __init__(self, paths: Iterable[str]) -> None:
        # Preserve insertion order for deterministic event ordering while
        # still deduplicating, because callers often pass glob results that
        # contain repeats.
        seen: Dict[str, None] = {}
        for path in paths:
            seen[path] = None
        self._paths: List[str] = list(seen.keys())
        self._signatures: Dict[str, Optional[Tuple[int, int]]] = {}
        self._primed = False

    @property
    def paths(self) -> Tuple[str, ...]:
        """The paths this watcher observes, in construction order."""

        return tuple(self._paths)

    @staticmethod
    def _signature(path: str) -> Optional[Tuple[int, int]]:
        """Return a cheap change signature, or ``None`` if the path is absent.

        ``FileNotFoundError`` is the expected case for a missing path.  We
        let other ``OSError`` subclasses propagate because they indicate a
        real problem (permissions, invalid path) rather than a normal poll
        result.
        """

        try:
            st = os.stat(path)
        except FileNotFoundError:
            return None
        return (st.st_mtime_ns, st.st_size)

    def prime(self) -> None:
        """Record the current state without emitting events.

        Call this after construction if you want the first :meth:`poll` to
        report only changes that happen after you started watching, rather
        than reporting every existing path as created.
        """

        self._signatures = {path: self._signature(path) for path in self._paths}
        self._primed = True

    def poll(self) -> List[FileEvent]:
        """Compare current state with the last recorded state.

        On the first call, if :meth:`prime` has not been called, every path
        that currently exists is reported as ``created``.  This matches the
        mental model of "I started watching and these files appeared".
        """

        if not self._primed:
            self._signatures = {path: None for path in self._paths}
            self._primed = True

        events: List[FileEvent] = []
        for path in self._paths:
            old = self._signatures.get(path)
            new = self._signature(path)
            self._signatures[path] = new

            if old is None and new is not None:
                events.append(FileEvent(path, FileEventType.CREATED, new))
            elif old is not None and new is None:
                events.append(FileEvent(path, FileEventType.DELETED, None))
            elif old is not None and new is not None and old != new:
                events.append(FileEvent(path, FileEventType.MODIFIED, new))
        return events
