import os
from datetime import datetime, timedelta, timezone, date
from db import get_db, execute_pipeline
from pymongo.errors import ConnectionFailure

PERIOD_MAP = {
    "today": 0,
    "week": 7,
    "month": 30,
}

def _date_range(period: str) -> tuple:
    period = period.strip().lower()
    today = date.today()
    if period in PERIOD_MAP:
        days = PERIOD_MAP[period]
        end = today
        start = today - timedelta(days=days)
        return start.isoformat(), end.isoformat()
    if ":" in period:
        parts = period.split(":")
        if len(parts) == 2:
            return parts[0].strip(), parts[1].strip()
    raise ValueError(f"Invalid period: {period}. Use: today, week, month, YYYY-MM-DD:YYYY-MM-DD")

def _build_attendance_pipeline(start: str, end: str, employee_name: str = None) -> list:
    start_dt = datetime.fromisoformat(start).replace(tzinfo=timezone.utc)
    end_dt = datetime.fromisoformat(end).replace(tzinfo=timezone.utc) + timedelta(days=1) - timedelta(seconds=1)
    pipeline = [
        {"$match": {"date": {"$gte": start_dt, "$lte": end_dt}}},
        {"$lookup": {
            "from": "employees",
            "localField": "employeeId",
            "foreignField": "_id",
            "as": "employee",
        }},
        {"$unwind": {"path": "$employee", "preserveNullAndEmptyArrays": True}},
        {"$project": {
            "_id": 0,
            "employeeName": "$employee.fullName",
            "department": "$employee.department",
            "position": "$employee.position",
            "date": 1,
            "clockIn": 1,
            "clockOut": 1,
            "workHours": 1,
            "otHours": 1,
            "lateMinutes": 1,
            "undertimeMinutes": 1,
            "notes": 1,
            "status": {"$cond": [{"$gt": ["$lateMinutes", 0]}, "LATE", {"$cond": [{"$gt": ["$undertimeMinutes", 0]}, "UNDERTIME", "ON_TIME"]}]},
        }},
        {"$sort": {"date": 1}},
    ]
    if employee_name:
        pipeline.insert(3, {"$match": {"employee.fullName": {"$regex": employee_name, "$options": "i"}}})
    return pipeline

def _build_summary_pipeline(start: str, end: str) -> list:
    start_dt = datetime.fromisoformat(start).replace(tzinfo=timezone.utc)
    end_dt = datetime.fromisoformat(end).replace(tzinfo=timezone.utc) + timedelta(days=1) - timedelta(seconds=1)
    return [
        {"$match": {"date": {"$gte": start_dt, "$lte": end_dt}}},
        {"$lookup": {
            "from": "employees",
            "localField": "employeeId",
            "foreignField": "_id",
            "as": "employee",
        }},
        {"$unwind": {"path": "$employee", "preserveNullAndEmptyArrays": True}},
        {"$group": {
            "_id": "$employeeId",
            "fullName": {"$first": "$employee.fullName"},
            "department": {"$first": "$employee.department"},
            "totalWorkHours": {"$sum": "$workHours"},
            "totalOtHours": {"$sum": "$otHours"},
            "avgLateMinutes": {"$avg": "$lateMinutes"},
            "lateDays": {"$sum": {"$cond": [{"$gt": ["$lateMinutes", 0]}, 1, 0]}},
            "undertimeDays": {"$sum": {"$cond": [{"$gt": ["$undertimeMinutes", 0]}, 1, 0]}},
            "totalDays": {"$sum": 1},
        }},
        {"$sort": {"totalWorkHours": -1}},
    ]

def _format_attendance_report(results: list, start: str, end: str, summary: bool = False, employee_name: str = None) -> str:
    if not results:
        if employee_name:
            return f"Employee '{employee_name}' not found for period {start} to {end}."
        return f"No timelogs found for period {start} to {end}."
    if summary:
        lines = [f"Attendance Summary ({start} to {end}):"]
        for r in results:
            lines.append(f"  {r.get('fullName', 'Unknown')} ({r.get('department', 'N/A')}): {r.get('totalWorkHours', 0):.1f}h worked, "
                         f"{r.get('totalOtHours', 0):.1f}h OT, {r.get('lateDays', 0)} late days, {r.get('undertimeDays', 0)} undertime days")
        return "\n".join(lines)
    lines = [f"Attendance Report ({start} to {end}):"]
    for r in results:
        clock_in = r.get("clockIn", "N/A")
        clock_out = r.get("clockOut", "N/A")
        lines.append(f"  {r.get('employeeName', 'Unknown')}: {str(r.get('date', ''))[:10]} {clock_in}-{clock_out} "
                     f"({r.get('workHours', 0):.1f}h) [{r.get('status', 'N/A')}]")
    return "\n".join(lines)

def get_attendance_report(period: str = "today", employee: str = None) -> dict:
    try:
        start, end = _date_range(period)
    except ValueError as e:
        return {"report": str(e), "raw": [], "collection": "timelogs", "pipeline": []}
    pipeline = _build_attendance_pipeline(start, end, employee)
    try:
        db = get_db()
        results = execute_pipeline(db, "timelogs", pipeline)
    except (ValueError, ConnectionFailure) as e:
        return {"report": f"Database error: {e}", "raw": [], "collection": "timelogs", "pipeline": pipeline}
    report = _format_attendance_report(results, start, end, employee_name=employee)
    return {"report": report, "raw": results, "collection": "timelogs", "pipeline": pipeline}

def get_attendance_summary(period: str = "month") -> dict:
    try:
        start, end = _date_range(period)
    except ValueError as e:
        return {"report": str(e), "raw": [], "collection": "timelogs", "pipeline": []}
    pipeline = _build_summary_pipeline(start, end)
    try:
        db = get_db()
        results = execute_pipeline(db, "timelogs", pipeline)
    except (ValueError, ConnectionFailure) as e:
        return {"report": f"Database error: {e}", "raw": [], "collection": "timelogs", "pipeline": pipeline}
    report = _format_attendance_report(results, start, end, summary=True)
    return {"report": report, "raw": results, "collection": "timelogs", "pipeline": pipeline}
