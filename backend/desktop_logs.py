from datetime import datetime, timedelta
import logging
import re
from threading import Lock

from app.database import CHINA


class DailyLog:
    encoding = "utf-8"

    def __init__(self, folder, prefix):
        self.folder = folder
        self.prefix = prefix
        self.lock = Lock()
        self.day = None
        self.stream = None
        self.rollover()

    def _rollover(self):
        today = datetime.now(CHINA).date()
        if self.day != today:
            stream = (self.folder / f"{self.prefix}_{today:%Y%m%d}.log").open("a", encoding=self.encoding, buffering=1)
            if self.stream is not None:
                self.stream.close()
            self.day, self.stream = today, stream

    def rollover(self):
        with self.lock:
            self._rollover()

    def write(self, text):
        with self.lock:
            self._rollover()
            return self.stream.write(text)

    def flush(self):
        with self.lock:
            if self.stream is not None:
                self.stream.flush()

    def isatty(self):
        return False

    def close(self):
        with self.lock:
            if self.stream is not None:
                self.stream.close()
                self.stream = None


def remove_old_logs(folder, today, retention_days):
    cutoff = today.toordinal() - retention_days
    for path in folder.iterdir():
        match = re.fullmatch(r"(?:console|server)_(\d{8})\.log", path.name)
        if not match or path.is_symlink() or not path.is_file():
            continue
        try:
            day = datetime.strptime(match[1], "%Y%m%d").date()
        except ValueError:
            continue
        if day.toordinal() < cutoff:
            try:
                path.unlink(missing_ok=True)
            except OSError:
                logging.exception("清理日志失败：%s", path.name)


def maintain_logs(folder, streams, cleanup_time, retention_days, stopped):
    next_cleanup = datetime.combine(datetime.now(CHINA).date(), cleanup_time, CHINA)
    while not stopped.wait(max(0, (next_cleanup - datetime.now(CHINA)).total_seconds())):
        try:
            for stream in streams:
                stream.rollover()
            remove_old_logs(folder, datetime.now(CHINA).date(), retention_days)
        except OSError:
            logging.exception("清理日志失败")
        next_cleanup = datetime.combine(datetime.now(CHINA).date() + timedelta(days=1), cleanup_time, CHINA)
