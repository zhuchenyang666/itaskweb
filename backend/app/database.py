from datetime import datetime, timedelta, timezone
from pathlib import Path
from threading import Lock

from sqlalchemy import create_engine, event, select
from sqlalchemy.orm import Session

from .models import AccountBase, User, WorkBase, TaskType, GeneralSettings

CHINA = timezone(timedelta(hours=8))


class Database:
    def __init__(self, root: Path):
        self.root = root
        root.mkdir(parents=True, exist_ok=True)
        self.accounts = self._engine(root / "accounts.sqlite3")
        self.years = {}
        self.lock = Lock()

    @staticmethod
    def _engine(path, wal=True):
        engine = create_engine(f"sqlite:///{path.as_posix()}", connect_args={"check_same_thread": False, "timeout": 15})

        @event.listens_for(engine, "connect")
        def configure(connection, _):
            connection.execute("PRAGMA foreign_keys=ON")
            connection.execute("PRAGMA journal_mode=" + ("WAL" if wal else "DELETE"))

        return engine

    def year_engine(self, year: int):
        if type(year) is not int or not 1900 <= year <= 2100:
            raise ValueError("年份必须在1900至2100之间")
        with self.lock:
            if year not in self.years:
                folder = self.root / str(year)
                folder.mkdir(exist_ok=True)
                engine = self._engine(folder / "worktime.sqlite3", wal=False)
                WorkBase.metadata.create_all(engine)
                # 同时限制直接 ORM 写入，防止日期写进错误年份的文件。
                with engine.begin() as connection:
                    for action in ("INSERT", "UPDATE"):
                        connection.exec_driver_sql(
                            f"CREATE TRIGGER IF NOT EXISTS year_guard_{action.lower()} BEFORE {action} ON work_records "
                            f"WHEN strftime('%Y', NEW.work_date) IS NULL OR strftime('%Y', NEW.work_date) != '{year}' "
                            "BEGIN SELECT RAISE(ABORT, 'work date must match database year'); END"
                        )
                self.years[year] = engine
            return self.years[year]

    def initialize(self):
        AccountBase.metadata.create_all(self.accounts)
        from .excel_export import TASK_TYPES
        with Session(self.accounts) as db:
            if db.get(GeneralSettings, 1) is None:
                db.add(GeneralSettings(id=1))
                db.commit()
            if not db.scalar(select(TaskType.id).limit(1)):
                db.add_all(TaskType(name=name, aliases=[name], is_leave=name == "年假") for name in TASK_TYPES)
                db.commit()
        for index in User.__table__.indexes:
            index.create(self.accounts, checkfirst=True)
        self.year_engine(datetime.now(CHINA).year)
        for folder in self.root.iterdir():
            if folder.is_dir() and folder.name.isdigit() and 1900 <= int(folder.name) <= 2100:
                self.year_engine(int(folder.name))

    def session(self):
        with Session(self.accounts) as session:
            yield session

    def close(self):
        self.accounts.dispose()
        for engine in self.years.values():
            engine.dispose()
