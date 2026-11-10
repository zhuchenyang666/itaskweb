from datetime import date
import calendar
from decimal import Decimal
from typing import Annotated, Literal

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from fastapi.responses import Response
from pydantic import BaseModel, Field, ConfigDict, field_validator
from sqlalchemy import select, delete, or_, func, text, cast, String
from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError

from .auth import current_user, get_db, public_user
from .models import User, LoginSession, WorkRecord, TaskType, GeneralSettings
from .security import hash_password
from .excel_export import build_export_workbook, ExportValidationError, parse_payload, calculate_statistics

router = APIRouter(prefix="/api", tags=["业务"])
Year = Annotated[int, Query(ge=1900, le=2100)]

def admin(user=Depends(current_user)):
    if user.role != "admin":
        raise HTTPException(403, "仅管理员可操作")
    return user

class ProfileInput(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)
    name: str = Field(min_length=1, max_length=80)
    position: str = Field(min_length=1, max_length=80)

@router.put("/profile")
def profile(body: ProfileInput, user=Depends(current_user), db: Session=Depends(get_db)):
    user.name, user.position = body.name, body.position
    db.commit()
    return public_user(user)

@router.get("/users")
def users(keyword: str="", _: User=Depends(admin), db: Session=Depends(get_db)):
    query = select(User).order_by(User.id)
    if keyword:
        query = query.where(or_(User.username.contains(keyword, autoescape=True), User.name.contains(keyword, autoescape=True)))
    return [dict(public_user(u), is_active=u.is_active) for u in db.scalars(query)]

class CreateUserInput(BaseModel):
    username: str = Field(pattern=r"^[A-Za-z]+$", max_length=64)
    name: str | None = Field(default=None, min_length=1, max_length=80)


@router.post("/users", status_code=201)
def add_user(body: CreateUserInput, _: User=Depends(admin), db: Session=Depends(get_db)):
    user = User(username=body.username.lower(), name=body.name or body.username.lower(), password_hash=hash_password("123456"))
    db.add(user)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(409, "账号已被使用，停用账号也不能重复添加")
    return {"message": "用户已添加，初始密码为123456"}

def ordinary_user(db, user_id):
    target = db.get(User, user_id)
    if not target:
        raise HTTPException(404, "用户不存在")
    if target.role == "admin":
        raise HTTPException(400, "不能对管理员执行此操作")
    return target

@router.delete("/users/{user_id}", status_code=204)
def disable_user(user_id: int, _: User=Depends(admin), db: Session=Depends(get_db)):
    target = ordinary_user(db, user_id)
    target.is_active = False
    db.execute(delete(LoginSession).where(LoginSession.user_id == user_id))
    db.commit()

@router.post("/users/{user_id}/enable", status_code=204)
def enable_user(user_id: int, _: User=Depends(admin), db: Session=Depends(get_db)):
    target = ordinary_user(db, user_id)
    target.is_active = True
    db.commit()


@router.post("/users/{user_id}/reset-password", status_code=204)
def reset_password(user_id: int, _: User=Depends(admin), db: Session=Depends(get_db)):
    target = ordinary_user(db, user_id)
    target.password_hash = hash_password("123456")
    target.must_change_password = True
    db.execute(delete(LoginSession).where(LoginSession.user_id == user_id))
    db.commit()

class RecordInput(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)
    user_id: int | None = Field(default=None, gt=0)
    work_date: date
    project: str = Field(min_length=1, max_length=200)
    task_type: str = Field(min_length=1, max_length=80)
    description: str = Field(min_length=1, max_length=4000)
    hours: Decimal = Field(ge=0, le=24, multiple_of=Decimal("0.1"))
    code_lines: int = Field(default=0, ge=0, le=10000000, strict=True)
    remark: str = Field(default="", max_length=2000)

    @field_validator("work_date")
    @classmethod
    def year_range(cls, value):
        if not 1900 <= value.year <= 2100:
            raise ValueError("年份必须在1900至2100之间")
        return value


def owned(record, user):
    if not record:
        raise HTTPException(404, "记录不存在")
    if user.role != "admin" and record.user_id != user.id:
        raise HTTPException(403, "不能操作其他人的工时")
    return record

def values(body, user, accounts, previous=None):
    target_id = body.user_id if user.role == "admin" and body.user_id else user.id
    if user.role != "admin" and body.user_id not in (None, user.id):
        raise HTTPException(403, "不能为其他人填报")
    target = accounts.get(User, target_id)
    if not target:
        raise HTTPException(400, "填报人不存在")
    if target.role == "admin":
        raise HTTPException(422, "管理员不参与工时填报，请选择普通用户")
    known = accounts.scalar(select(TaskType).where(TaskType.name == body.task_type, TaskType.is_active.is_(True)))
    if not known and (previous is None or previous.task_type != body.task_type):
        raise HTTPException(422, "任务类型不存在或已删除，请刷新后重新选择")
    result = body.model_dump(exclude={"hours"})
    result["user_id"] = target_id
    result["hours_tenths"] = int(body.hours * 10)
    return result

def record_dict(record, people):
    owner = people.get(record.user_id)
    return dict(id=record.id, user_id=record.user_id, work_date=record.work_date.isoformat(),
                project=record.project, task_type=record.task_type, description=record.description,
                hours=record.hours_tenths / 10, code_lines=record.code_lines, remark=record.remark,
                name=owner.name if owner else "未知用户", username=owner.username if owner else "",
                is_active=owner.is_active if owner else False)

@router.get("/options")
def options(_: User=Depends(current_user), db: Session=Depends(get_db)):
    return {"task_types": list(db.scalars(select(TaskType.name).where(TaskType.is_active.is_(True)).order_by(TaskType.id)))}


class SettingsInput(BaseModel):
    standard_hours: Decimal = Field(ge=Decimal("0.1"), le=24, multiple_of=Decimal("0.1"))
    annual_leave_days: Decimal = Field(ge=0, le=365, multiple_of=Decimal("0.5"))


@router.get("/settings")
def get_settings(_: User=Depends(admin), db: Session=Depends(get_db)):
    settings = db.get(GeneralSettings, 1)
    return {"standard_hours": float(settings.standard_hours), "annual_leave_days": float(settings.annual_leave_days)}


@router.put("/settings")
def update_settings(body: SettingsInput, _: User=Depends(admin), db: Session=Depends(get_db)):
    settings = db.get(GeneralSettings, 1)
    settings.standard_hours = body.standard_hours
    settings.annual_leave_days = body.annual_leave_days
    db.commit()
    return get_settings(_, db)


class TaskInput(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)
    name: str = Field(min_length=1, max_length=80, pattern=r"^[^=\x00-\x1f][^\x00-\x1f]*$")


@router.get("/tasks")
def tasks(_: User=Depends(admin), db: Session=Depends(get_db)):
    return [{"id": t.id, "name": t.name} for t in db.scalars(select(TaskType).where(TaskType.is_active.is_(True)).order_by(TaskType.id))]


def save_task(body, db, task=None):
    for other in db.scalars(select(TaskType)):
        if other is not task and body.name.casefold() in [a.casefold() for a in other.aliases]:
            raise HTTPException(409, "任务名称已存在或已用于历史记录")
    if task is None:
        task = TaskType(name=body.name, aliases=[body.name], is_leave=False)
        db.add(task)
    else:
        task.name = body.name
        task.aliases = list(dict.fromkeys(task.aliases + [body.name]))
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(409, "任务名称已存在")
    return {"id": task.id, "name": task.name}


@router.post("/tasks", status_code=201)
def add_task(body: TaskInput, _: User=Depends(admin), db: Session=Depends(get_db)):
    return save_task(body, db)


@router.put("/tasks/{task_id}")
def edit_task(task_id: int, body: TaskInput, _: User=Depends(admin), db: Session=Depends(get_db)):
    task = db.get(TaskType, task_id)
    if not task or not task.is_active:
        raise HTTPException(404, "任务不存在")
    return save_task(body, db, task)


@router.delete("/tasks/{task_id}", status_code=204)
def delete_task(task_id: int, _: User=Depends(admin), db: Session=Depends(get_db)):
    task = db.get(TaskType, task_id)
    if not task or not task.is_active:
        raise HTTPException(404, "任务不存在")
    task.is_active = False
    db.commit()

def filtered_records(year, month, day, keyword, include_inactive, people):
    if day and (not month or day > calendar.monthrange(year, month)[1]):
        raise HTTPException(422, "日必须属于所选年份和月份")
    query = select(WorkRecord)
    if not include_inactive:
        query = query.where(WorkRecord.user_id.in_([u.id for u in people.values() if u.is_active]))
    if month:
        query = query.where(func.strftime("%m", WorkRecord.work_date) == f"{month:02}")
    if day:
        query = query.where(func.strftime("%d", WorkRecord.work_date) == f"{day:02}")
    if keyword:
        ids = [u.id for u in people.values() if keyword.casefold() in (u.name + (" 已停用" if not u.is_active else "")).casefold()]
        query = query.where(or_(WorkRecord.project.contains(keyword, autoescape=True),
                               WorkRecord.description.contains(keyword, autoescape=True),
                               WorkRecord.task_type.contains(keyword, autoescape=True),
                               WorkRecord.remark.contains(keyword, autoescape=True),
                               cast(WorkRecord.work_date, String).contains(keyword, autoescape=True),
                               cast(WorkRecord.code_lines, String).contains(keyword, autoescape=True),
                               cast(WorkRecord.hours_tenths / 10.0, String).contains(keyword, autoescape=True),
                               WorkRecord.user_id.in_(ids)))
    return query

@router.get("/records")
def records(request: Request, year: Year, month: int | None=Query(None, ge=1, le=12),
            day: int | None=Query(None, ge=1, le=31), keyword: str=Query("", max_length=200),
            page: int=Query(1, ge=1), page_size: int=Query(10, ge=1, le=100), include_inactive: bool=True,
            user: User=Depends(current_user), accounts: Session=Depends(get_db)):
    people = {u.id: u for u in accounts.scalars(select(User))}
    query = filtered_records(year, month, day, keyword, include_inactive, people)
    if user.role != "admin":
        query = query.where(WorkRecord.user_id == user.id)
    with Session(request.app.state.database.year_engine(year)) as db:
        total = db.scalar(select(func.count()).select_from(query.subquery()))
        hours = db.scalar(select(func.sum(query.subquery().c.hours_tenths))) or 0
        rows = db.scalars(query.order_by(WorkRecord.work_date.desc(), WorkRecord.id.desc()).offset((page-1)*page_size).limit(page_size))
        return {"items": [record_dict(r, people) for r in rows], "total": total, "hours": hours/10}

@router.post("/records", status_code=201)
def add_record(body: RecordInput, request: Request, user: User=Depends(current_user), accounts: Session=Depends(get_db)):
    data = values(body, user, accounts)
    with Session(request.app.state.database.year_engine(body.work_date.year)) as db:
        record = WorkRecord(**data)
        db.add(record)
        db.commit()
        return {"id": record.id, "year": body.work_date.year}

@router.get("/records/suggestions")
def record_suggestions(request: Request, field: Literal["project", "description", "remark"],
                       user_id: int | None=Query(None, gt=0), q: str=Query("", max_length=4000),
                       user: User=Depends(current_user)):
    if user.role != "admin" and user_id not in (None, user.id):
        raise HTTPException(403, "不能查看他人的填写历史")

    column = getattr(WorkRecord, field)
    limit = 8
    query = (select(column)
             .where(WorkRecord.user_id == (user_id or user.id), column != "")
             .group_by(column)
             .order_by(func.max(WorkRecord.work_date).desc(), func.max(WorkRecord.id).desc())
             .limit(limit))
    if q.strip():
        query = query.where(column.contains(q.strip(), autoescape=True))

    database = request.app.state.database
    with database.lock:
        years = sorted(database.years, reverse=True)
    suggestions = {}
    for year in years:
        with Session(database.year_engine(year)) as db:
            suggestions.update(dict.fromkeys(db.scalars(query)))
        if len(suggestions) >= limit:
            break
    return list(suggestions)[:limit]


@router.put("/records/{year}/{record_id}")
def edit_record(year: int, record_id: int, body: RecordInput, request: Request,
                user: User=Depends(current_user), accounts: Session=Depends(get_db)):
    if not 1900 <= year <= 2100:
        raise HTTPException(422, "年份无效")
    database = request.app.state.database
    source = database.year_engine(year)
    with Session(source) as db:
        previous = owned(db.get(WorkRecord, record_id), user)
        if body.user_id is None:
            body = body.model_copy(update={"user_id": previous.user_id})
        data = values(body, user, accounts, previous)
        if year == body.work_date.year:
            record = db.get(WorkRecord, record_id)
            for key, value in data.items():
                setattr(record, key, value)
            db.commit()
            return {"id": record_id, "year": year}
    # ATTACH将两个年份的修改纳入同一事务，失败时同时回滚。
    target = database.year_engine(body.work_date.year)
    with source.connect() as connection:
        connection.exec_driver_sql("ATTACH DATABASE ? AS destination", (str(target.url.database),))
        connection.commit()
        try:
            with Session(bind=connection) as db, db.begin():
                previous = owned(db.get(WorkRecord, record_id), user)
                parameters = dict(data, work_date=data["work_date"].isoformat(), created_at=previous.created_at)
                inserted = db.execute(text("INSERT INTO destination.work_records (user_id,work_date,project,task_type,description,hours_tenths,code_lines,remark,created_at,updated_at) VALUES (:user_id,:work_date,:project,:task_type,:description,:hours_tenths,:code_lines,:remark,:created_at,CURRENT_TIMESTAMP)"), parameters)
                new_id = inserted.lastrowid
                db.execute(delete(WorkRecord).where(WorkRecord.id == record_id))
        finally:
            connection.exec_driver_sql("DETACH DATABASE destination")
            connection.commit()
    return {"id": new_id, "year": body.work_date.year}

@router.delete("/records/{year}/{record_id}", status_code=204)
def remove_record(year: int, record_id: int, request: Request, user: User=Depends(current_user)):
    if not 1900 <= year <= 2100:
        raise HTTPException(422, "年份无效")
    with Session(request.app.state.database.year_engine(year)) as db:
        record = owned(db.get(WorkRecord, record_id), user)
        db.delete(record)
        db.commit()

def annual_payload(request, year, include_inactive, accounts):
    people = {u.id: u for u in accounts.scalars(select(User)) if u.role != "admin" and (include_inactive or u.is_active)}
    with Session(request.app.state.database.year_engine(year)) as db:
        query = filtered_records(year, None, None, "", include_inactive, people).where(WorkRecord.user_id.in_(people))
        rows = list(db.scalars(query.order_by(WorkRecord.work_date, WorkRecord.id)))
        config = {}
        settings = accounts.get(GeneralSettings, 1)
        config["standardHours"] = float(settings.standard_hours)
        config["annualLeaveDays"] = float(settings.annual_leave_days)
        task_rows = list(accounts.scalars(select(TaskType)))
        leave_names = {a for t in task_rows if t.is_leave for a in t.aliases}
        config["taskTypes"] = list(dict.fromkeys([a for t in task_rows for a in t.aliases] + [r.task_type for r in rows] + ["年假"]))
        def safe_text(value):
            return "'" + value if value.startswith("=") else value
        names = {uid: safe_text(f"{u.name}({u.username})") for uid, u in people.items()}
        config["people"] = list(names.values())
        import chinese_calendar
        try:
            holidays = chinese_calendar.get_holidays(date(year, 1, 1), date(year, 12, 31), include_weekends=False)
        except NotImplementedError as exc:
            raise HTTPException(400, str(exc))
        config["holidays"] = [d.isoformat() for d in holidays]
        return {"config": config, "entries": [dict(date=r.work_date.isoformat(), person=names[r.user_id], project=safe_text(r.project),
            taskType="年假" if r.task_type in leave_names else r.task_type, description=safe_text(r.description), hours=r.hours_tenths/10, codeLines=r.code_lines, note=safe_text(r.remark)) for r in rows]}


@router.get("/statistics")
def statistics(request: Request, year: Year, include_inactive: bool=False, _: User=Depends(admin), accounts: Session=Depends(get_db)):
    payload = annual_payload(request, year, include_inactive, accounts)
    if not payload["entries"]:
        return None
    try:
        config, entries = parse_payload(payload)
        return calculate_statistics(config, entries)
    except ExportValidationError as exc:
        raise HTTPException(400, str(exc))


@router.get("/export")
def export(request: Request, year: Year, include_inactive: bool=False, _: User=Depends(admin), accounts: Session=Depends(get_db)):
    try:
        content = build_export_workbook(annual_payload(request, year, include_inactive, accounts))
    except (ExportValidationError, ValueError) as exc:
        raise HTTPException(400, str(exc))
    return Response(content.getvalue(), media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                             headers={"Content-Disposition": f'attachment; filename="worktime-{year}.xlsx"'})
