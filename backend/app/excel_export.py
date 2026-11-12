from __future__ import annotations

import calendar
import io
import math
import unicodedata
from collections import defaultdict
from dataclasses import dataclass
from datetime import date, datetime
from typing import Any, Iterable

import chinese_calendar
from openpyxl import Workbook, load_workbook
from openpyxl.formatting.rule import CellIsRule
from openpyxl.styles import Alignment, Border, Font, PatternFill, Protection, Side
from openpyxl.utils import get_column_letter


TASK_TYPES = ["需求分析", "架构设计", "编码开发", "单元测试", "Bug修复", "联调对接", "文档编写", "会议沟通", "年假", "其他"]
DETAIL_HEADERS = ["序号", "填报日期", "所属项目", "任务类型", "任务内容描述", "花费时间(小时)", "有效代码行数", "填报人", "备注"]

BLUE = "4472C4"
BLUE_DARK = "305496"
CONFIG_GREEN = "70AD47"
CONFIG_YELLOW = "FFF2CC"
SECTION_ORANGE = "ED7D31"
WHITE = "FFFFFF"
BLACK = "000000"
GRID = "D9D9D9"
GREEN = "C6EFCE"
YELLOW = "FFD966"
RED = "FF0000"


class ExportValidationError(ValueError):
    pass


@dataclass(frozen=True)
class Entry:
    work_date: date
    project: str
    task_type: str
    description: str
    hours: float
    code_lines: int
    person: str
    note: str

    @property
    def is_leave(self) -> bool:
        return self.task_type == "年假"


@dataclass(frozen=True)
class Config:
    standard_hours: float
    annual_leave_days: float
    holidays: frozenset[date]
    people: tuple[str, ...]
    projects: tuple[str, ...]
    task_types: tuple[str, ...]


def _split_items(value: Any) -> list[str]:
    if isinstance(value, list):
        raw = value
    else:
        raw = str(value or "").replace("，", ",").split(",")
    result: list[str] = []
    for item in raw:
        text = str(item).strip()
        if text and text not in result:
            result.append(text)
    return result


def _parse_date(value: Any, label: str) -> date:
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    text = str(value or "").strip().replace("/", "-")
    try:
        return datetime.strptime(text, "%Y-%m-%d").date()
    except ValueError as exc:
        raise ExportValidationError(f"{label}格式无效，应为 YYYY-MM-DD") from exc


def _number(value: Any, label: str, *, integer: bool = False) -> float | int:
    try:
        number = float(value)
    except (TypeError, ValueError) as exc:
        raise ExportValidationError(f"{label}必须是数字") from exc
    if not math.isfinite(number):
        raise ExportValidationError(f"{label}必须是有限数字")
    if number < 0:
        raise ExportValidationError(f"{label}不能为负数")
    if integer and not number.is_integer():
        raise ExportValidationError(f"{label}必须是整数")
    return int(number) if integer else number


def _validate_step(number: float, step: float, label: str) -> None:
    if not math.isclose(number / step, round(number / step), abs_tol=1e-9):
        raise ExportValidationError(f"{label}必须按 {step:g} 的步长填写")


def parse_payload(payload: dict[str, Any], allow_empty: bool = False) -> tuple[Config, list[Entry]]:
    raw_config = payload.get("config") or {}
    standard_hours = float(_number(raw_config.get("standardHours", 10), "标准日工时"))
    if not 0.1 <= standard_hours <= 24:
        raise ExportValidationError("标准日工时必须在 0.1–24.0 小时之间")
    _validate_step(standard_hours, 0.1, "标准日工时")
    annual_leave_days = float(_number(raw_config.get("annualLeaveDays", 7), "年度年假总额"))
    if annual_leave_days > 365:
        raise ExportValidationError("年度年假总额必须在 0–365 天之间")
    _validate_step(annual_leave_days, 0.5, "年度年假总额")
    holidays = frozenset(
        _parse_date(item, f"节假日“{item}”")
        for item in _split_items(raw_config.get("holidays", []))
    )
    configured_people = _split_items(raw_config.get("people", []))
    configured_task_types = _split_items(raw_config.get("taskTypes", TASK_TYPES))

    entries: list[Entry] = []
    for index, raw in enumerate(payload.get("entries") or [], start=1):
        if not any(str(value or "").strip() for value in raw.values()):
            continue
        required = {
            "date": "填报日期",
            "project": "所属项目",
            "taskType": "任务类型",
            "description": "任务内容描述",
            "person": "填报人",
        }
        for key, label in required.items():
            if not str(raw.get(key) or "").strip():
                raise ExportValidationError(f"第 {index} 行“{label}”不能为空")
        hours = float(_number(raw.get("hours"), f"第 {index} 行花费时间"))
        if hours > 24:
            raise ExportValidationError(f"第 {index} 行花费时间必须在 0.0–24.0 小时之间")
        _validate_step(hours, 0.1, f"第 {index} 行花费时间")
        code_lines = int(_number(raw.get("codeLines", 0) or 0, f"第 {index} 行有效代码行数", integer=True))
        if code_lines > 10_000_000:
            raise ExportValidationError(f"第 {index} 行有效代码行数必须在 0–10,000,000 之间")
        entry = Entry(
            work_date=_parse_date(raw.get("date"), f"第 {index} 行填报日期"),
            project=str(raw["project"]).strip(),
            task_type=str(raw["taskType"]).strip(),
            description=str(raw["description"]).strip(),
            hours=hours,
            code_lines=code_lines,
            person=str(raw["person"]).strip(),
            note=str(raw.get("note") or "").strip(),
        )
        if entry.task_type not in configured_task_types:
            raise ExportValidationError(f"第 {index} 行任务类型不在维护选项中")
        if entry.person not in configured_people:
            raise ExportValidationError(f"第 {index} 行填报人不在维护选项中")
        entries.append(entry)

    if not entries and not allow_empty:
        raise ExportValidationError("请至少填写一条工时记录")

    return (
        Config(
            standard_hours=standard_hours,
            annual_leave_days=annual_leave_days,
            holidays=holidays,
            people=tuple(configured_people),
            projects=tuple(dict.fromkeys(entry.project for entry in entries)),
            task_types=tuple(configured_task_types),
        ),
        entries,
    )


def _workdays(start: date, end: date, holidays: frozenset[date]) -> int:
    days = 0
    current = start.toordinal()
    while current <= end.toordinal():
        day = date.fromordinal(current)
        if day not in holidays:
            if day.weekday() < 5:
                days += 1
            else:
                try:
                    days += chinese_calendar.is_workday(day)
                except NotImplementedError:
                    pass
        current += 1
    return days


def _month_bounds(year: int, month: int) -> tuple[date, date]:
    return date(year, month, 1), date(year, month, calendar.monthrange(year, month)[1])


def calculate_statistics(config: Config, entries: list[Entry], year: int | None = None) -> dict[str, Any]:
    months = [(year, month) for month in range(1, 13)] if year is not None else sorted({(entry.work_date.year, entry.work_date.month) for entry in entries})
    years = [year] if year is not None else sorted({entry.work_date.year for entry in entries})
    # Leave entries are valid work-hour records for attendance and saturation.
    # They remain excluded from project/code投入统计 below.
    productive = [entry for entry in entries if not entry.is_leave]
    active_people = sorted(config.people if year is not None else {entry.person for entry in entries})
    productive_people = {entry.person for entry in productive}

    actual_month_person: dict[tuple[int, int, str], float] = defaultdict(float)
    leave_month_person: dict[tuple[int, int, str], float] = defaultdict(float)
    actual_year_person: dict[tuple[int, str], float] = defaultdict(float)
    leave_year_person: dict[tuple[int, str], float] = defaultdict(float)
    for entry in entries:
        month_key = (entry.work_date.year, entry.work_date.month, entry.person)
        year_key = (entry.work_date.year, entry.person)
        actual_month_person[month_key] += entry.hours
        actual_year_person[year_key] += entry.hours
        if entry.is_leave:
            leave_month_person[month_key] += entry.hours / config.standard_hours
            leave_year_person[year_key] += entry.hours / config.standard_hours

    personal_monthly = []
    for year, month in months:
        start, end = _month_bounds(year, month)
        month_workdays = _workdays(start, end, config.holidays)
        holiday_count = sum(1 for day in config.holidays if start <= day <= end and day.weekday() < 5)
        for person in active_people:
            leave_days = round(leave_month_person[(year, month, person)], 1)
            capacity_hours = month_workdays * config.standard_hours
            actual_hours = actual_month_person[(year, month, person)]
            personal_monthly.append(
                {
                    "month": f"{year:04d}-{month:02d}",
                    "person": person,
                    "workdays": month_workdays,
                    "holidays": holiday_count,
                    "leaveDays": leave_days,
                    "expectedHours": capacity_hours,
                    "capacityHours": capacity_hours,
                    "actualHours": actual_hours,
                    "saturation": actual_hours / capacity_hours if capacity_hours else 0,
                }
            )

    team_monthly = []
    for year, month in months:
        rows = [row for row in personal_monthly if row["month"] == f"{year:04d}-{month:02d}"]
        # Team saturation uses calendar capacity; annual leave must not reduce its denominator.
        capacity = sum(row["capacityHours"] for row in rows)
        actual = sum(row["actualHours"] for row in rows)
        team_monthly.append(
            {"month": f"{year:04d}-{month:02d}", "expectedHours": capacity, "actualHours": actual, "saturation": actual / capacity if capacity else 0}
        )

    personal_yearly = []
    for year in years:
        start, end = date(year, 1, 1), date(year, 12, 31)
        year_workdays = _workdays(start, end, config.holidays)
        for person in active_people:
            leave_days = round(leave_year_person[(year, person)], 1)
            capacity_hours = year_workdays * config.standard_hours
            actual_hours = actual_year_person[(year, person)]
            personal_yearly.append(
                {
                    "year": year,
                    "person": person,
                    "workdays": year_workdays,
                    "leaveDays": leave_days,
                    "expectedHours": capacity_hours,
                    "capacityHours": capacity_hours,
                    "actualHours": actual_hours,
                    "saturation": actual_hours / capacity_hours if capacity_hours else 0,
                }
            )

    team_yearly = []
    for year in years:
        rows = [row for row in personal_yearly if row["year"] == year]
        # Team saturation uses calendar capacity; annual leave must not reduce its denominator.
        capacity = sum(row["capacityHours"] for row in rows)
        actual = sum(row["actualHours"] for row in rows)
        team_yearly.append(
            {"year": year, "expectedHours": capacity, "actualHours": actual, "saturation": actual / capacity if capacity else 0}
        )

    project_rows = []
    all_projects = list(dict.fromkeys(entry.project for entry in productive))
    for project in all_projects:
        matched = [entry for entry in productive if entry.project == project]
        total_hours = sum(entry.hours for entry in matched)
        participants = len({entry.person for entry in matched})
        project_rows.append(
            {
                "project": project,
                "hours": total_hours,
                "codeLines": sum(entry.code_lines for entry in matched),
                "participants": participants,
                "averageHours": total_hours / participants if participants else 0,
            }
        )

    all_task_types = list(config.task_types)
    for entry in entries:
        if entry.task_type not in all_task_types:
            all_task_types.append(entry.task_type)
    total_recorded_hours = sum(entry.hours for entry in entries)
    task_rows = []
    for task_type in all_task_types:
        hours = sum(entry.hours for entry in entries if entry.task_type == task_type)
        task_rows.append({"taskType": task_type, "hours": hours, "share": hours / total_recorded_hours if total_recorded_hours else 0})

    return {
        "teamMonthly": team_monthly,
        "teamYearly": team_yearly,
        "projects": project_rows,
        "tasks": task_rows,
        "personalMonthly": personal_monthly,
        "personalYearly": personal_yearly,
        "totalHours": sum(entry.hours for entry in entries),
        "totalCodeLines": sum(entry.code_lines for entry in productive),
        "peopleCount": len(active_people),
        "productivePeopleCount": len(productive_people),
        "projectCount": len({entry.project for entry in productive}),
    }


def build_preview(payload: dict[str, Any]) -> dict[str, Any]:
    config, entries = parse_payload(payload)
    stats = calculate_statistics(config, entries)
    latest = stats["teamMonthly"][-1]
    return {
        "records": len(entries),
        "totalHours": stats["totalHours"],
        "totalCodeLines": stats["totalCodeLines"],
        "peopleCount": stats["peopleCount"],
        "projectCount": stats["projectCount"],
        "latestMonth": latest["month"],
        "latestSaturation": latest["saturation"],
    }


def _apply_header(cells: Iterable[Any]) -> None:
    thin = Side(style="thin", color=WHITE)
    for cell in cells:
        cell.fill = PatternFill("solid", fgColor=BLUE)
        cell.font = Font(name="微软雅黑", color=WHITE, bold=True, size=11)
        cell.alignment = Alignment(horizontal="center", vertical="center", wrap_text=True)
        cell.border = Border(left=thin, right=thin, top=thin, bottom=thin)


def _apply_body(cells: Iterable[Any]) -> None:
    thin = Side(style="thin", color=GRID)
    locked_fill = PatternFill("solid", fgColor=CONFIG_YELLOW)
    font = Font(name="微软雅黑", size=10)
    alignment = Alignment(horizontal="center", vertical="center", wrap_text=True)
    border = Border(left=thin, right=thin, top=thin, bottom=thin)
    for cell in cells:
        cell.font = font
        cell.alignment = alignment
        cell.border = border
        cell.fill = locked_fill


def _apply_visible_grid(ws: Any, max_row: int, max_col: int = 14) -> None:
    """Write real cell borders so blank areas look consistent in Excel and WPS."""
    thin = Side(style="thin", color=GRID)
    grid_border = Border(left=thin, right=thin, top=thin, bottom=thin)
    for row in ws.iter_rows(min_row=1, max_row=max_row, min_col=1, max_col=max_col):
        for cell in row:
            sides = (cell.border.left, cell.border.right, cell.border.top, cell.border.bottom)
            if not any(getattr(side, "style", None) for side in sides):
                cell.border = grid_border


def _apply_outer_border(
    ws: Any,
    min_row: int,
    max_row: int,
    min_col: int,
    max_col: int,
    *,
    color: str = BLUE_DARK,
) -> None:
    outer = Side(style="medium", color=color)

    def set_sides(cell: Any, *, left: Side | None = None, right: Side | None = None, top: Side | None = None, bottom: Side | None = None) -> None:
        targets = [cell]
        for merged_range in ws.merged_cells.ranges:
            if cell.coordinate in merged_range:
                master = ws.cell(merged_range.min_row, merged_range.min_col)
                if master.coordinate != cell.coordinate:
                    targets.append(master)
                break
        for target in targets:
            current = target.border
            target.border = Border(
                left=left or current.left,
                right=right or current.right,
                top=top or current.top,
                bottom=bottom or current.bottom,
                diagonal=current.diagonal,
                diagonal_direction=current.diagonal_direction,
                diagonalUp=current.diagonalUp,
                diagonalDown=current.diagonalDown,
                outline=current.outline,
                vertical=current.vertical,
                horizontal=current.horizontal,
            )

    for column in range(min_col, max_col + 1):
        set_sides(ws.cell(min_row, column), top=outer)
        set_sides(ws.cell(max_row, column), bottom=outer)
    for row in range(min_row, max_row + 1):
        set_sides(ws.cell(row, min_col), left=outer)
        set_sides(ws.cell(row, max_col), right=outer)


def _write_section(
    ws: Any,
    row: int,
    title: str,
    headers: list[str],
    values: list[list[Any]],
    widths: list[float],
    *,
    min_data_rows: int = 0,
    gap_rows: int = 3,
    subsection: bool = False,
) -> int:
    end_col = len(headers)
    ws.merge_cells(start_row=row, start_column=1, end_row=row, end_column=end_col)
    title_cell = ws.cell(row, 1, title)
    if subsection:
        title_cell.font = Font(name="微软雅黑", color=BLACK, bold=True, size=11)
        title_cell.alignment = Alignment(horizontal="center", vertical="center")
    else:
        title_cell.fill = PatternFill("solid", fgColor=BLUE_DARK)
        title_cell.font = Font(name="微软雅黑", color=WHITE, bold=True, size=12)
        title_cell.alignment = Alignment(horizontal="center", vertical="center")
    ws.row_dimensions[row].height = 25
    header_row = row + 1
    for col, header in enumerate(headers, 1):
        ws.cell(header_row, col, header)
    _apply_header(ws[header_row][:end_col])
    ws.row_dimensions[header_row].height = 34
    data_row = header_row + 1
    for row_values in values:
        for col, value in enumerate(row_values, 1):
            ws.cell(data_row, col, value)
        _apply_body(ws[data_row][:end_col])
        ws.row_dimensions[data_row].height = 23
        data_row += 1
    for _ in range(max(0, min_data_rows - len(values))):
        _apply_body(ws[data_row][:end_col])
        ws.row_dimensions[data_row].height = 23
        data_row += 1
    for col, width in enumerate(widths, 1):
        ws.column_dimensions[get_column_letter(col)].width = max(ws.column_dimensions[get_column_letter(col)].width or 0, width)
    _apply_outer_border(ws, row, data_row - 1, 1, end_col)
    return data_row + gap_rows


def _write_primary_banner(ws: Any, row: int, title: str, end_col: int) -> None:
    ws.merge_cells(start_row=row, start_column=1, end_row=row, end_column=end_col)
    cell = ws.cell(row, 1, title)
    cell.fill = PatternFill("solid", fgColor=SECTION_ORANGE)
    cell.font = Font(name="微软雅黑", color=WHITE, bold=True, size=12)
    cell.alignment = Alignment(horizontal="center", vertical="center")
    ws.row_dimensions[row].height = 25
    _apply_outer_border(ws, row, row, 1, end_col)


def _set_formula(cell: Any, formula: str, *, number_format: str | None = None) -> None:
    cell.value = formula
    cell.fill = PatternFill("solid", fgColor=CONFIG_YELLOW)
    if number_format:
        cell.number_format = number_format


def _apply_saturation_fill(cell: Any, value: float) -> None:
    if value > 1:
        color = RED
    elif value < 0.8:
        color = YELLOW
    else:
        color = GREEN
    cell.fill = PatternFill("solid", fgColor=color)


def _write_formula_hint(ws: Any, title_row: int, table_end_col: int, lines: list[str]) -> None:
    hint_col = table_end_col + 1
    header = ws.cell(title_row, hint_col, "计算公式提示")
    header.fill = PatternFill("solid", fgColor=BLUE_DARK)
    header.font = Font(name="微软雅黑", color=WHITE, bold=True, size=10)
    header.alignment = Alignment(horizontal="center", vertical="center")
    body = ws.cell(title_row + 1, hint_col, "\n".join(lines))
    body.fill = PatternFill("solid", fgColor=CONFIG_YELLOW)
    body.font = Font(name="微软雅黑", size=10)
    body.alignment = Alignment(horizontal="left", vertical="center", wrap_text=True)
    ws.column_dimensions[get_column_letter(hint_col)].width = max(
        ws.column_dimensions[get_column_letter(hint_col)].width or 0,
        48,
    )
    ws.row_dimensions[title_row + 1].height = max(
        ws.row_dimensions[title_row + 1].height or 0,
        max(48, 22 * len(lines)),
    )
    _apply_outer_border(ws, title_row, title_row + 1, hint_col, hint_col)


def _add_detail_worksheet(wb: Workbook, entries: list[Entry]) -> None:
    ws = wb.active
    ws.title = "工时打卡明细"
    ws.append(DETAIL_HEADERS)
    _apply_header(ws[1])
    ws.row_dimensions[1].height = 32
    widths = [6, 14, 26, 22, 60, 12, 12, 40, 44]
    for column, width in enumerate(widths, 1):
        ws.column_dimensions[get_column_letter(column)].width = width
    for index, entry in enumerate(entries, 1):
        ws.append(
            [
                index,
                entry.work_date,
                entry.project,
                entry.task_type,
                entry.description,
                entry.hours,
                entry.code_lines,
                entry.person,
                entry.note,
            ]
        )
        row = index + 1
        _apply_body(ws.cell(row, column) for column in range(1, len(DETAIL_HEADERS) + 1))
        ws.row_dimensions[row].height = 30
        ws.cell(row, 2).number_format = "yyyy-mm-dd"
        ws.cell(row, 6).number_format = "0.0"
    detail_rows = max(20, len(entries))
    for row in range(len(entries) + 2, detail_rows + 2):
        _apply_body(ws[row][:len(DETAIL_HEADERS)])
        ws.row_dimensions[row].height = 24
    ws.auto_filter.ref = f"A1:I{detail_rows + 1}"
    ws.sheet_view.showGridLines = True
    _apply_outer_border(ws, 1, detail_rows + 1, 1, len(DETAIL_HEADERS))
    _apply_visible_grid(ws, max_row=max(100, detail_rows + 1))


def _add_summary_worksheet(wb: Workbook, config: Config, stats: dict[str, Any]) -> None:
    ws = wb.create_sheet()
    ws.title = "数据统计汇总"
    ws.sheet_view.showGridLines = True

    ws.merge_cells("A1:B1")
    ws["A1"] = "基础配置"
    ws["A1"].fill = PatternFill("solid", fgColor=CONFIG_GREEN)
    ws["A1"].font = Font(name="微软雅黑", color=WHITE, bold=True, size=12)
    ws["A1"].alignment = Alignment(horizontal="center", vertical="center")
    config_rows = [
        ("标准日工时（小时/天）", config.standard_hours),
        ("年度年假总额（天/人/年）", config.annual_leave_days),
        ("法定节假日配置（逗号分隔）", ",".join(sorted(day.isoformat() for day in config.holidays))),
        ("填报人员（逗号分隔）", ",".join(config.people)),
        ("填报项目（自动汇总）", ",".join(config.projects)),
        ("任务类型（逗号分隔）", ",".join(config.task_types)),
    ]
    for label, value in config_rows:
        ws.append([label, value])
        _apply_body(ws[ws.max_row][:2])
    yellow_fill = PatternFill("solid", fgColor=CONFIG_YELLOW)
    for cell in ("B2", "B3"):
        ws[cell].fill = yellow_fill
        ws[cell].alignment = Alignment(horizontal="center", vertical="center", wrap_text=True)
    for config_row in range(4, 8):
        ws.merge_cells(start_row=config_row, start_column=2, end_row=config_row, end_column=8)
        ws.cell(config_row, 2).fill = yellow_fill
        ws.cell(config_row, 2).alignment = Alignment(horizontal="center", vertical="center", wrap_text=True)
    ws.column_dimensions["A"].width = 24
    ws.column_dimensions["B"].width = 24
    ws.row_dimensions[2].height = 28
    ws.row_dimensions[3].height = 28
    ws.row_dimensions[4].height = 34
    ws.row_dimensions[5].height = 40
    ws.row_dimensions[6].height = 64
    ws.row_dimensions[7].height = 64
    _apply_outer_border(ws, 1, 7, 1, 8, color=CONFIG_GREEN)

    row = 10
    saturation_ranges: list[str] = []
    percentage_ranges: list[str] = []
    _write_primary_banner(ws, row, "一、全员团队饱和度统计", 4)
    row += 2
    section_start = row
    monthly_rows = max(12, len(stats["teamMonthly"]))
    row = _write_section(
        ws,
        row,
        "1.1 全员月度饱和度",
        ["统计月份", "全员应出勤总工时(小时)", "全员实际总工时(小时)", "团队月饱和度"],
        [[item["month"], item["expectedHours"], item["actualHours"], item["saturation"]] for item in stats["teamMonthly"]],
        [16, 25, 25, 18],
        min_data_rows=monthly_rows,
        subsection=True,
    )
    monthly_data_start = section_start + 2
    for offset, item in enumerate(stats["teamMonthly"]):
        data_row = monthly_data_start + offset
        saturation_cell = ws.cell(data_row, 4)
        _set_formula(saturation_cell, f"=IFERROR(C{data_row}/B{data_row},0)", number_format="0.00%")
        _apply_saturation_fill(saturation_cell, item["saturation"])
    _write_formula_hint(
        ws,
        section_start,
        4,
        ["团队月饱和度 = 全员实际总工时 ÷ 全员应出勤总工时"],
    )
    saturation_ranges.append(f"D{section_start + 2}:D{section_start + 1 + monthly_rows}")

    section_start = row
    yearly_rows = max(6, len(stats["teamYearly"]))
    row = _write_section(
        ws,
        row,
        "1.2 全员年度饱和度",
        ["统计年份", "全年应出勤总工时(小时)", "全年实际总工时(小时)", "团队年度饱和度"],
        [[item["year"], item["expectedHours"], item["actualHours"], item["saturation"]] for item in stats["teamYearly"]],
        [16, 25, 25, 18],
        min_data_rows=yearly_rows,
        subsection=True,
    )
    yearly_data_start = section_start + 2
    for offset, item in enumerate(stats["teamYearly"]):
        data_row = yearly_data_start + offset
        saturation_cell = ws.cell(data_row, 4)
        _set_formula(saturation_cell, f"=IFERROR(C{data_row}/B{data_row},0)", number_format="0.00%")
        _apply_saturation_fill(saturation_cell, item["saturation"])
    _write_formula_hint(
        ws,
        section_start,
        4,
        ["团队年度饱和度 = 全年实际总工时 ÷ 全年应出勤总工时"],
    )
    saturation_ranges.append(f"D{section_start + 2}:D{section_start + 1 + yearly_rows}")
    section_start = row
    project_rows = max(10, len(stats["projects"]) + 1)
    row = _write_section(
        ws,
        row,
        "二、按项目投入统计",
        ["项目名称", "总投入工时(小时)", "总代码行数", "参与人数", "人均工时(小时)"],
        [[item["project"], item["hours"], item["codeLines"], item["participants"], item["averageHours"]] for item in stats["projects"]]
        + [[
            "合计",
            sum(item["hours"] for item in stats["projects"]),
            sum(item["codeLines"] for item in stats["projects"]),
            stats["productivePeopleCount"],
            stats["totalHours"] / stats["productivePeopleCount"] if stats["productivePeopleCount"] else 0,
        ]],
        [26, 20, 17, 13, 20],
        min_data_rows=project_rows,
    )
    project_data_start = section_start + 2
    project_data_end = project_data_start + len(stats["projects"]) - 1
    for data_row in range(project_data_start, project_data_end + 1):
        _set_formula(ws.cell(data_row, 5), f"=IFERROR(B{data_row}/D{data_row},0)", number_format="0.0")
    project_total_row = project_data_end + 1
    if stats["projects"]:
        _set_formula(ws.cell(project_total_row, 2), f"=SUM(B{project_data_start}:B{project_data_end})", number_format="0.0")
        _set_formula(ws.cell(project_total_row, 3), f"=SUM(C{project_data_start}:C{project_data_end})", number_format="#,##0")
    _set_formula(ws.cell(project_total_row, 5), f"=IFERROR(B{project_total_row}/D{project_total_row},0)", number_format="0.0")
    _write_formula_hint(
        ws,
        section_start,
        5,
        [
            "人均工时 = 总投入工时 ÷ 参与人数",
            "合计工时、代码行数 = 各项目数据之和",
        ],
    )
    section_start = row
    task_rows = max(12, len(stats["tasks"]))
    row = _write_section(
        ws,
        row,
        "三、按任务类型工时占比",
        ["任务类型", "总工时(小时)", "工时占比"],
        [[item["taskType"], item["hours"], item["share"]] for item in stats["tasks"]],
        [22, 20, 17],
        min_data_rows=task_rows,
    )
    task_data_start = section_start + 2
    task_data_end = task_data_start + len(stats["tasks"]) - 1
    for data_row in range(task_data_start, task_data_end + 1):
        _set_formula(
            ws.cell(data_row, 3),
            f"=IFERROR(B{data_row}/SUM($B${task_data_start}:$B${task_data_end}),0)",
            number_format="0.00%",
        )
    _write_formula_hint(
        ws,
        section_start,
        3,
        ["工时占比 = 当前任务类型工时 ÷ 全部任务类型总工时"],
    )
    percentage_ranges.append(f"C{section_start + 2}:C{section_start + 1 + task_rows}")
    section_start = row
    personal_monthly_rows = max(15, len(stats["personalMonthly"]))
    row = _write_section(
        ws,
        row,
        "四、个人月度工作饱和度统计",
        ["统计月份", "填报人", "当月应出勤工作日(天)", "当月工作日放假(天)", "当月已休年假(天)", "应出勤总工时(小时)", "当月实际工时(小时)", "工作饱和度"],
        [[item["month"], item["person"], item["workdays"], item["holidays"], item["leaveDays"], item["expectedHours"], item["actualHours"], item["saturation"]] for item in stats["personalMonthly"]],
        [15, 14, 23, 22, 20, 22, 22, 16],
        min_data_rows=personal_monthly_rows,
    )
    personal_monthly_start = section_start + 2
    for offset, item in enumerate(stats["personalMonthly"]):
        data_row = personal_monthly_start + offset
        _set_formula(ws.cell(data_row, 6), f"=C{data_row}*$B$2", number_format="0.0")
        saturation_cell = ws.cell(data_row, 8)
        _set_formula(saturation_cell, f"=IFERROR(G{data_row}/(C{data_row}*$B$2),0)", number_format="0.00%")
        _apply_saturation_fill(saturation_cell, item["saturation"])
    _write_formula_hint(
        ws,
        section_start,
        8,
        [
            "应出勤总工时 = 当月应出勤工作日 × 标准日工时",
            "工作饱和度 = 当月实际工时 ÷ 应出勤总工时",
            "年假任务工时计入当月实际工时；已休年假按年假工时 ÷ 标准日工时折算，保留 1 位小数",
        ],
    )
    saturation_ranges.append(f"H{section_start + 2}:H{section_start + 1 + personal_monthly_rows}")
    section_start = row
    personal_yearly_rows = max(10, len(stats["personalYearly"]))
    row = _write_section(
        ws,
        row,
        "五、单人年度工作饱和度统计",
        ["统计年份", "姓名", "全年应出勤工作日(天)", "全年已休年假(天)", "全年应出勤总工时(小时)", "全年实际总工时(小时)", "年度工作饱和度"],
        [[item["year"], item["person"], item["workdays"], item["leaveDays"], item["expectedHours"], item["actualHours"], item["saturation"]] for item in stats["personalYearly"]],
        [15, 14, 23, 20, 24, 24, 18],
        min_data_rows=personal_yearly_rows,
    )
    personal_yearly_start = section_start + 2
    for offset, item in enumerate(stats["personalYearly"]):
        data_row = personal_yearly_start + offset
        _set_formula(ws.cell(data_row, 5), f"=C{data_row}*$B$2", number_format="0.0")
        saturation_cell = ws.cell(data_row, 7)
        _set_formula(saturation_cell, f"=IFERROR(F{data_row}/(C{data_row}*$B$2),0)", number_format="0.00%")
        _apply_saturation_fill(saturation_cell, item["saturation"])
    _write_formula_hint(
        ws,
        section_start,
        7,
        [
            "全年应出勤总工时 = 全年应出勤工作日 × 标准日工时",
            "年度工作饱和度 = 全年实际工时 ÷ 全年应出勤总工时",
            "年假任务工时计入全年实际工时；已休年假按年假工时 ÷ 标准日工时折算，保留 1 位小数",
        ],
    )
    saturation_ranges.append(f"G{section_start + 2}:G{section_start + 1 + personal_yearly_rows}")

    instruction_start = row
    row = _write_section(
        ws,
        row,
        "六、填报说明",
        ["说明", "", "", "", "", "", "", ""],
        [
            ["【工时统计说明】本工作簿由工时管理系统生成；导出的统计工作簿所有单元格均可编辑", None, None, None, None, None, None, None],
            ["1. 管理员可在通用设置中维护标准日工时、年度年假总额和任务类型", None, None, None, None, None, None, None],
            ["2. 团队成员在工时记录页面填报和修改数据；修正后按年份重新导出年度统计", None, None, None, None, None, None, None],
            ["3. 休年假时选择年假任务类型；个人月度和年度数据自动统计", None, None, None, None, None, None, None],
            ["4. 全员及个人月度/年度饱和度均根据全年填报数据自动计算，无需在统计工作簿中手动填写", None, None, None, None, None, None, None],
            ["5. 颜色说明：绿色=饱和度80%-100%（正常），红色=>100%（加班/负荷过高），黄色=<80%（负荷不足）", None, None, None, None, None, None, None],
        ],
        [24, 22, 20, 18, 20, 20, 20, 16],
        min_data_rows=6,
        gap_rows=0,
    )
    for instruction_row in range(instruction_start + 2, instruction_start + 8):
        ws.merge_cells(start_row=instruction_row, start_column=1, end_row=instruction_row, end_column=8)
        ws.cell(instruction_row, 1).alignment = Alignment(horizontal="center", vertical="center", wrap_text=True)
        ws.row_dimensions[instruction_row].height = 38
    _apply_outer_border(ws, instruction_start, instruction_start + 7, 1, 8)

    summary_widths = [24, 22, 20, 18, 20, 20, 20, 16]
    for col, width in enumerate(summary_widths, 1):
        ws.column_dimensions[get_column_letter(col)].width = width
    for cell_range in percentage_ranges:
        for row_cells in ws[cell_range]:
            for cell in row_cells:
                cell.number_format = "0.00%"
    # All saturation ranges use the same traffic-light thresholds as the template.
    for cell_range in saturation_ranges:
        for row_cells in ws[cell_range]:
            for cell in row_cells:
                cell.number_format = "0.00%"
        ws.conditional_formatting.add(cell_range, CellIsRule(operator="greaterThan", formula=["1"], stopIfTrue=True, fill=PatternFill("solid", fgColor=RED)))
        ws.conditional_formatting.add(cell_range, CellIsRule(operator="between", formula=["0.8", "1"], stopIfTrue=True, fill=PatternFill("solid", fgColor=GREEN)))
        ws.conditional_formatting.add(cell_range, CellIsRule(operator="lessThan", formula=["0.8"], stopIfTrue=True, fill=PatternFill("solid", fgColor=YELLOW)))
    ws.print_options.horizontalCentered = True
    ws.page_setup.orientation = "landscape"
    ws.page_setup.fitToWidth = 1
    for column, width in enumerate([30, 44, 22, 20, 20, 22, 22, 18], 1):
        ws.column_dimensions[get_column_letter(column)].width = width
    _apply_visible_grid(ws, max_row=ws.max_row + 20)


def _fit_row_heights(ws: Any) -> None:
    merged = {}
    for area in ws.merged_cells.ranges:
        width = sum(ws.column_dimensions[get_column_letter(col)].width for col in range(area.min_col, area.max_col + 1))
        merged[(area.min_row, area.min_col)] = (width, area.max_row - area.min_row + 1)
    for row in ws.iter_rows():
        height = ws.row_dimensions[row[0].row].height or 23
        for cell in row:
            if not isinstance(cell.value, str) or cell.data_type == "f":
                continue
            width, span = merged.get((cell.row, cell.column), (ws.column_dimensions[cell.column_letter].width, 1))
            usable = max(1, width - 2)
            lines = sum(max(1, math.ceil(sum(2 if unicodedata.east_asian_width(ch) in "WF" else 1 for ch in line) / usable)) for line in cell.value.split("\n"))
            height = max(height, ((cell.font.sz or 10) * 1.5 * lines + 10) / span)
        ws.row_dimensions[row[0].row].height = min(409, height)


def build_export_workbook(payload: dict[str, Any]) -> io.BytesIO:
    config, entries = parse_payload(payload)
    stats = calculate_statistics(config, entries)
    workbook = Workbook()
    _add_detail_worksheet(workbook, entries)
    _add_summary_worksheet(workbook, config, stats)
    protection = Protection(locked=False, hidden=False)
    for worksheet in workbook:
        _fit_row_heights(worksheet)
        for row in worksheet:
            for cell in row:
                cell.protection = protection
    workbook.calculation.calcMode = "auto"
    workbook.calculation.fullCalcOnLoad = True
    workbook.calculation.forceFullCalc = True

    output = io.BytesIO()
    workbook.save(output)
    output.seek(0)
    return output


def verify_workbook_has_formulas(content: bytes) -> bool:
    workbook = load_workbook(io.BytesIO(content), data_only=False)
    return any(
        cell.data_type == "f"
        for worksheet in workbook.worksheets
        for row in worksheet.iter_rows()
        for cell in row
    )
