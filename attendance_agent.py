import os
import datetime
from db import get_db, execute_pipeline

PERIOD_MAP = {
    "today": 0,
    "week": 7,
    "month": 30,
}

def _date_range(period: str) -> tuple:
    period = period.strip().lower()
    today = datetime.date.today()
    if period in PERIOD_MAP:
        days = PERIOD_MAP[period]
        end = today
        start = today - datetime.timedelta(days=days)
        return start.isoformat(), end.isoformat()
    if ":" in period:
        parts = period.split(":")
        if len(parts) == 2:
            return parts[0].strip(), parts[1].strip()
    raise ValueError(f"Invalid period: {period}. Use: today, week, month, YYYY-MM-DD:YYYY-MM-DD")

def _build_attendance_pipeline(start: str, end: str, employee_name: str = None) -> list:
    pipeline = [
        {"$match": {"date": {"$gte": {"$date": f"{start}T00:00:00Z"}, "$lte": {"$date": f"{end}T23:59:59Z"}}}},
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
        pipeline[0]["$match"]["employee.fullName"] = {"$regex": employee_name, "$options": "i"}
    return pipeline

def _build_summary_pipeline(start: str, end: str) -> list:
    return [
        {"$match": {"date": {"$gte": {"$date": f"{start}T00:00:00Z"}, "$lte": {"$date": f"{end}T23:59:59Z"}}}},
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

def _format_attendance_report(results: list, start: str, end: str, summary: bool = False) -> str:
    if not results:
        return f"No timelogs found for period {start} to {end}."
    if summary:
        lines = [f"Attendance Summary ({start} to {end}):"]
        for r in results:
            lines.append(f"  {r['fullName']} ({r['department']}): {r['totalWorkHours']:.1f}h worked, "
                         f"{r['totalOtHours']:.1f}h OT, {r['lateDays']} late days, {r['undertimeDays']} undertime days")
        return "\n".join(lines)
    lines = [f"Attendance Report ({start} to {end}):"]
    for r in results:
        clock_in = r.get("clockIn", "N/A")
        clock_out = r.get("clockOut", "N/A")
        lines.append(f"  {r['employeeName']}: {r['date'][:10]} {clock_in}-{clock_out} "
                     f"({r['workHours']:.1f}h) [{r['status']}]")
    return "\n".join(lines)

def get_attendance_report(period: str = "today", employee: str = None) -> dict:
    try:
        start, end = _date_range(period)
    except ValueError as e:
        return {"report": str(e), "raw": [], "collection": "timelogs", "pipeline": []}
    pipeline = _build_attendance_pipeline(start, end, employee)
    db = get_db()
    results = execute_pipeline(db, "timelogs", pipeline)
    report = _format_attendance_report(results, start, end)
    return {"report": report, "raw": results, "collection": "timelogs", "pipeline": pipeline}

def get_attendance_summary(period: str = "month") -> dict:
    try:
        start, end = _date_range(period)
    except ValueError as e:
        return {"report": str(e), "raw": [], "collection": "timelogs", "pipeline": []}
    pipeline = _build_summary_pipeline(start, end)
    db = get_db()
    results = execute_pipeline(db, "timelogs", pipeline)
    report = _format_attendance_report(results, start, end, summary=True)
    return {"report": report, "raw": results, "collection": "timelogs", "pipeline": pipeline}
