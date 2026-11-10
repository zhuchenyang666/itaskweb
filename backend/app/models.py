from datetime import date, datetime, timezone

from sqlalchemy import Boolean, CheckConstraint, Date, DateTime, ForeignKey, Index, Integer, String, Text, text, JSON, Numeric
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


def utc_now():
    return datetime.now(timezone.utc).replace(tzinfo=None)


class AccountBase(DeclarativeBase):
    pass


class User(AccountBase):
    __tablename__ = "users"
    __table_args__ = (
        CheckConstraint("role IN ('admin', 'user')"),
        Index("uq_single_admin", "role", unique=True, sqlite_where=text("role = 'admin'")),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    username: Mapped[str] = mapped_column(String(64, collation="NOCASE"), unique=True)
    password_hash: Mapped[str] = mapped_column(String(256))
    name: Mapped[str] = mapped_column(String(80))
    position: Mapped[str] = mapped_column(String(80), default="普工")
    role: Mapped[str] = mapped_column(String(10), default="user")
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    must_change_password: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now)


class GeneralSettings(AccountBase):
    __tablename__ = "general_settings"
    __table_args__ = (CheckConstraint("standard_hours BETWEEN 0.1 AND 24"), CheckConstraint("annual_leave_days BETWEEN 0 AND 365"))
    id: Mapped[int] = mapped_column(primary_key=True)
    standard_hours: Mapped[float] = mapped_column(Numeric(4, 1), default=10)
    annual_leave_days: Mapped[float] = mapped_column(Numeric(4, 1), default=7)


class TaskType(AccountBase):
    __tablename__ = "task_types"
    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(80, collation="NOCASE"), unique=True)
    aliases: Mapped[list[str]] = mapped_column(JSON)
    is_leave: Mapped[bool] = mapped_column(Boolean, default=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)


class LoginSession(AccountBase):
    __tablename__ = "login_sessions"

    token_hash: Mapped[str] = mapped_column(String(64), primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    expires_at: Mapped[datetime] = mapped_column(DateTime, index=True)


class WorkBase(DeclarativeBase):
    pass


class WorkRecord(WorkBase):
    __tablename__ = "work_records"
    __table_args__ = (
        CheckConstraint("hours_tenths BETWEEN 0 AND 240"),
        CheckConstraint("code_lines BETWEEN 0 AND 10000000"),
        CheckConstraint("user_id > 0"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    # 用户在独立账号库中，跨 SQLite 文件的关联由服务层校验。
    user_id: Mapped[int] = mapped_column(Integer, index=True)
    work_date: Mapped[date] = mapped_column(Date, index=True)
    project: Mapped[str] = mapped_column(String(200))
    task_type: Mapped[str] = mapped_column(String(80))
    description: Mapped[str] = mapped_column(Text)
    hours_tenths: Mapped[int] = mapped_column(Integer)
    code_lines: Mapped[int] = mapped_column(Integer, default=0)
    remark: Mapped[str] = mapped_column(Text, default="")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now, onupdate=utc_now)
