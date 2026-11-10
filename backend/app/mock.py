from datetime import date
from itertools import islice, product
from random import Random
from string import ascii_lowercase
import calendar
import csv
import chinese_calendar
from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from .models import User, WorkRecord, LoginSession, GeneralSettings, TaskType
from .security import hash_password
from .settings import ROOT

PEOPLE = [
    (f"示例员工{i:02d}", f"demo{first}{second}", f"worker{first}{second}")
    for i, (first, second) in enumerate(islice(product(ascii_lowercase, repeat=2), 32), start=1)
]
roster = ROOT / "mock/roster.csv"
if roster.is_file():
    with roster.open(encoding="utf-8-sig", newline="") as file:
        PEOPLE = [tuple(row) for row in csv.reader(file) if row]

def mock_hours(index, day, standard, leave=False):
    if leave:
        return standard
    # 个人分低/中/高负荷，月份循环淡季/常态/高峰；单条记录仍不超过24小时。
    ratio = (0.74, 0.92, 1.10)[index % 3] * (0.78, 1.0, 1.20)[(day.month - 1) % 3]
    jitter = Random(f"hours-{day.isoformat()}-{index}").uniform(-0.015, 0.015)
    return max(1, min(240, round(standard * (ratio + jitter))))


def rebalance_mock(database):
    with Session(database.accounts) as db:
        settings = db.get(GeneralSettings, 1)
        standard = round(float(settings.standard_hours) * 10)
        order = {username: index for index, (_, _, username) in enumerate(PEOPLE)}
        people = {u.id: order[u.username] for u in db.scalars(select(User)) if u.username in order}
        leave_names = {a for task in db.scalars(select(TaskType).where(TaskType.is_leave.is_(True))) for a in task.aliases}
    count = 0
    for folder in database.root.iterdir():
        if folder.is_dir() and folder.name.isdigit() and 1900 <= int(folder.name) <= 2100:
            with Session(database.year_engine(int(folder.name))) as work:
                rows = work.scalars(select(WorkRecord).where(WorkRecord.user_id.in_(people), WorkRecord.remark == "模拟数据，仅供测试", WorkRecord.description.startswith("模拟工时：")))
                for row in rows:
                    row.hours_tenths = mock_hours(people[row.user_id], row.work_date, standard, row.task_type in leave_names)
                    count += 1
                work.commit()
    return count


def seed_mock(database, replace=False):
    if replace:
        for folder in database.root.iterdir():
            if folder.is_dir() and folder.name.isdigit() and 1900 <= int(folder.name) <= 2100:
                with Session(database.year_engine(int(folder.name))) as work:
                    work.execute(delete(WorkRecord))
                    work.commit()
        with Session(database.accounts) as db:
            db.execute(delete(LoginSession).where(LoginSession.user_id.in_(select(User.id).where(User.role != "admin"))))
            db.execute(delete(User).where(User.role != "admin"))
            db.commit()
    with Session(database.accounts) as db:
        old_accounts = [f"{legacy}@hengbao.com" for _, legacy, _ in PEOPLE]
        if db.scalar(select(User.id).where(User.username.in_(old_accounts)).limit(1)):
            raise ValueError("请先运行 migrate_accounts.py 迁移旧账号")
        settings = db.get(GeneralSettings, 1)
        standard = round(float(settings.standard_hours) * 10)
        annual_leave_days = float(settings.annual_leave_days)
        password = hash_password("123456")
        if not db.scalar(select(User).where(User.username == "admin")):
            db.add(User(username="admin", name="管理员", position="管理员", role="admin", password_hash=password))
        for name, _, username in PEOPLE:
            if not db.scalar(select(User).where(User.username == username)):
                db.add(User(username=username, name=name, position="普工", password_hash=password))
        db.commit()
        users = {u.username: u for u in db.scalars(select(User))}
        for year in (2025, 2026):
            with Session(database.year_engine(year)) as work:
                existing = set(work.scalars(select(WorkRecord.user_id)))
                for index, (_, legacy, username) in enumerate(PEOPLE):
                    person = users[username]
                    if person.id in existing:
                        continue
                    rng = Random(f"{year}-{legacy}")
                    leave_months = set((2, 5, 8, 11)[:min(4, int(annual_leave_days))])
                    for month in range(1, 13):
                        workdays = [date(year, month, day) for day in range(1, calendar.monthrange(year, month)[1]+1) if chinese_calendar.is_workday(date(year, month, day))]
                        for day_index, day in enumerate(workdays):
                            leave = month in leave_months and day_index == (index % len(workdays))
                            task = "年假" if leave else ["编码开发", "单元测试", "联调对接", "需求分析", "文档编写"][rng.randrange(5)]
                            hours = mock_hours(index, day, standard, leave)
                            code = rng.randint(80, 400) if task == "编码开发" else 0
                            work.add(WorkRecord(user_id=person.id, work_date=day,
                                project="年假" if leave else ["支付平台", "数据平台", "运维管理系统"][index % 3],
                                task_type=task, description="模拟工时：" + task,
                                hours_tenths=hours, code_lines=code, remark="模拟数据，仅供测试"))
                work.commit()
    write_roster(database.root)


def write_roster(root):
    with (root / "人员账号清单.csv").open("w", encoding="utf-8-sig", newline="") as file:
        writer = csv.writer(file)
        writer.writerow(["姓名", "账号", "职位"])
        writer.writerows((name, username, "普工") for name, _, username in PEOPLE)
