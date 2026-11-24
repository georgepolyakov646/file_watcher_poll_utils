import os
import tempfile
import unittest

from file_watcher_poll_utils import FileEvent, PollingFileWatcher
from file_watcher_poll_utils.core import FileEventType


class PollingFileWatcherTests(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.root = self._tmp.name

    def _path(self, name: str) -> str:
        return os.path.join(self.root, name)

    def test_first_poll_reports_existing_paths_as_created(self) -> None:
        path = self._path("a.txt")
        with open(path, "w", encoding="utf-8") as fh:
            fh.write("one")

        watcher = PollingFileWatcher([path])
        events = watcher.poll()

        self.assertEqual(len(events), 1)
        event = events[0]
        self.assertEqual(event.path, path)
        self.assertEqual(event.event_type, FileEventType.CREATED)
        self.assertIsNotNone(event.signature)

    def test_primed_watcher_does_not_report_existing_paths(self) -> None:
        path = self._path("a.txt")
        with open(path, "w", encoding="utf-8") as fh:
            fh.write("one")

        watcher = PollingFileWatcher([path])
        watcher.prime()
        self.assertEqual(watcher.poll(), [])

    def test_creation_after_prime_is_reported(self) -> None:
        path = self._path("new.txt")
        watcher = PollingFileWatcher([path])
        watcher.prime()

        with open(path, "w", encoding="utf-8") as fh:
            fh.write("hello")

        events = watcher.poll()
        self.assertEqual(len(events), 1)
        self.assertEqual(events[0].event_type, FileEventType.CREATED)
        self.assertEqual(events[0].path, path)
        self.assertIsNotNone(events[0].signature)

    def test_modification_is_reported_when_size_changes(self) -> None:
        path = self._path("a.txt")
        with open(path, "w", encoding="utf-8") as fh:
            fh.write("one")

        watcher = PollingFileWatcher([path])
        watcher.prime()

        with open(path, "w", encoding="utf-8") as fh:
            fh.write("one plus more")

        events = watcher.poll()
        self.assertEqual(len(events), 1)
        self.assertEqual(events[0].event_type, FileEventType.MODIFIED)
        self.assertEqual(events[0].path, path)

    def test_deletion_is_reported(self) -> None:
        path = self._path("a.txt")
        with open(path, "w", encoding="utf-8") as fh:
            fh.write("one")

        watcher = PollingFileWatcher([path])
        watcher.prime()
        os.remove(path)

        events = watcher.poll()
        self.assertEqual(len(events), 1)
        self.assertEqual(events[0].event_type, FileEventType.DELETED)
        self.assertIsNone(events[0].signature)

    def test_no_change_produces_no_events(self) -> None:
        path = self._path("a.txt")
        with open(path, "w", encoding="utf-8") as fh:
            fh.write("one")

        watcher = PollingFileWatcher([path])
        watcher.prime()
        self.assertEqual(watcher.poll(), [])
        self.assertEqual(watcher.poll(), [])

    def test_duplicate_paths_are_collapsed(self) -> None:
        path = self._path("a.txt")
        with open(path, "w", encoding="utf-8") as fh:
            fh.write("one")

        watcher = PollingFileWatcher([path, path, path])
        self.assertEqual(watcher.paths, (path,))
        self.assertEqual(len(watcher.poll()), 1)

    def test_paths_property_preserves_construction_order(self) -> None:
        first = self._path("first.txt")
        second = self._path("second.txt")
        watcher = PollingFileWatcher([second, first])
        self.assertEqual(watcher.paths, (second, first))

    def test_events_are_returned_in_path_order(self) -> None:
        first = self._path("first.txt")
        second = self._path("second.txt")
        watcher = PollingFileWatcher([first, second])
        watcher.prime()

        with open(first, "w", encoding="utf-8") as fh:
            fh.write("a")
        with open(second, "w", encoding="utf-8") as fh:
            fh.write("b")

        events = watcher.poll()
        self.assertEqual([e.path for e in events], [first, second])
        self.assertTrue(all(e.event_type is FileEventType.CREATED for e in events))

    def test_primed_missing_path_created_later(self) -> None:
        path = self._path("later.txt")
        watcher = PollingFileWatcher([path])
        watcher.prime()
        self.assertEqual(watcher.poll(), [])

        with open(path, "w", encoding="utf-8") as fh:
            fh.write("x")

        events = watcher.poll()
        self.assertEqual(len(events), 1)
        self.assertEqual(events[0].event_type, FileEventType.CREATED)

    def test_created_then_deleted_between_polls_reports_deleted(self) -> None:
        # A path that was absent at prime time, created, and then removed
        # before the next poll should look deleted only if it was seen in a
        # prior poll.  Here it was never seen, so no event is emitted.
        path = self._path("ghost.txt")
        watcher = PollingFileWatcher([path])
        watcher.prime()

        with open(path, "w", encoding="utf-8") as fh:
            fh.write("x")
        self.assertEqual(len(watcher.poll()), 1)
        os.remove(path)

        events = watcher.poll()
        self.assertEqual(len(events), 1)
        self.assertEqual(events[0].event_type, FileEventType.DELETED)

    def test_file_event_is_frozen(self) -> None:
        event = FileEvent("/tmp/x", FileEventType.CREATED, (1, 2))
        with self.assertRaises(Exception):
            event.path = "/tmp/y"  # type: ignore[misc]

    def test_signature_is_none_for_deleted_event(self) -> None:
        path = self._path("a.txt")
        with open(path, "w", encoding="utf-8") as fh:
            fh.write("one")

        watcher = PollingFileWatcher([path])
        watcher.prime()
        os.remove(path)
        events = watcher.poll()
        self.assertIsNone(events[0].signature)

    def test_poll_is_idempotent_after_deletion(self) -> None:
        path = self._path("a.txt")
        with open(path, "w", encoding="utf-8") as fh:
            fh.write("one")

        watcher = PollingFileWatcher([path])
        watcher.prime()
        os.remove(path)
        self.assertEqual(len(watcher.poll()), 1)
        self.assertEqual(watcher.poll(), [])


if __name__ == "__main__":
    unittest.main()
