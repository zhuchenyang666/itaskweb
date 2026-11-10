from contextlib import closing
from datetime import datetime, time, timedelta
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import Mock, patch

from desktop_logs import CHINA, DailyLog, maintain_logs, remove_old_logs


class Clock(datetime):
    current = datetime(2026, 11, 10, 23, 59, tzinfo=CHINA)

    @classmethod
    def now(cls, tz=None):
        return cls.current.astimezone(tz)


class DesktopLogTests(unittest.TestCase):
    def test_files_roll_at_midnight_while_open(self):
        with TemporaryDirectory() as folder, patch("desktop_logs.datetime", Clock):
            root = Path(folder)
            Clock.current = datetime(2026, 11, 10, 23, 59, tzinfo=CHINA)
            with closing(DailyLog(root, "server")) as server, closing(DailyLog(root, "console")) as console:
                server.write("before\n")
                console.write("before\n")
                Clock.current += timedelta(minutes=2)
                server.write("after\n")
                console.write("after\n")
            for prefix in ("server", "console"):
                self.assertEqual((root / f"{prefix}_20261110.log").read_text(), "before\n")
                self.assertEqual((root / f"{prefix}_20261111.log").read_text(), "after\n")

    def test_cleanup_keeps_boundary_and_unrelated_files(self):
        with TemporaryDirectory() as folder:
            root = Path(folder)
            keep = {"server_20261103.log", "console_20261110.log", "console.log", "check.json", "other_20261102.log"}
            for name in keep | {"console_20261102.log", "server_20261101.log"}:
                (root / name).touch()
            remove_old_logs(root, datetime(2026, 11, 10).date(), 7)
            self.assertEqual({path.name for path in root.iterdir()}, keep)

    def test_cleanup_waits_until_configured_time(self):
        Clock.current = datetime(2026, 11, 10, 0, 59, 30, tzinfo=CHINA)
        stopped, stream = Mock(), Mock()

        def wait(seconds):
            Clock.current += timedelta(seconds=seconds)
            return stopped.wait.call_count > 1

        stopped.wait.side_effect = wait
        with patch("desktop_logs.datetime", Clock), patch("desktop_logs.remove_old_logs") as cleanup:
            maintain_logs(Path("logs"), [stream], time(1, 0), 7, stopped)
        self.assertEqual([call.args for call in stopped.wait.call_args_list], [(30.0,), (86400.0,)])
        cleanup.assert_called_once_with(Path("logs"), datetime(2026, 11, 10).date(), 7)
        stream.rollover.assert_called_once()
