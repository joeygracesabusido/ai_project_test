# Automation Agents Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Add 3 specialized automation agents (attendance, funds, balance sheet) to the MongoDB CLI with `/command` routing.

**Architecture:** Pre-built MongoDB aggregation pipelines in dedicated modules routed via `agent.py` command parser. Each agent returns `{report, raw, collection, pipeline}` — same contract as existing `run_query()`. Zero LLM dependency for automation commands.

**Tech Stack:** Python 3.11+, pymongo, rich (unchanged)

---

### Task 1: Attendance Agent — Module

**Files:**
- Create: `attendance_agent.py`
- Create: `tests/test_attendance_agent.py`

**Step 1: Write failing tests**

`tests/test_attendance_agent.py`:
```python
import pytest
from unittest.mock import patch, MagicMock
from attendance_agent import get_attendance_report, get_attendance_summary, _date_range

class TestAttendanceAgent:
    def test_date_range_today(self):
        start, end = _date_range("today")
        assert start == end  # single day range

    def test_date_range_week(self):
        start, end = _date_range("week")
        assert start < end

    def test_date_range_month(self):
        start, end = _date_range("month")
        assert start < end

    def test_date_range_custom(self):
        start, end = _date_range("2026-01-01:2026-01-31")
        assert start == "2026-01-01"
        assert end == "2026-01-31"

    def test_date_range_invalid(self):
        with pytest.raises(ValueError, match="Invalid period"):
            _date_range("invalid")

    def test_attendance_report_returns_structure(self):
        with patch("attendance_agent.get_db") as mock_db, \
             patch("attendance_agent.execute_pipeline") as mock_exec:
            mock_db.return_value = MagicMock()
            mock_exec.return_value = [
                {"fullName": "Alice", "date": "2026-05-26", "workHours": 8.0}
            ]
            result = get_attendance_report("today")
            assert "report" in result
            assert "raw" in result
            assert "collection" in result
            assert result["collection"] == "timelogs"

    def test_attendance_report_empty(self):
        with patch("attendance_agent.get_db") as mock_db, \
             patch("attendance_agent.execute_pipeline") as mock_exec:
            mock_db.return_value = MagicMock()
            mock_exec.return_value = []
            result = get_attendance_report("today")
            assert "No timelogs" in result["report"]

    def test_attendance_summary_returns_structure(self):
        with patch("attendance_agent.get_db") as mock_db, \
             patch("attendance_agent.execute_pipeline") as mock_exec:
            mock_db.return_value = MagicMock()
            mock_exec.return_value = [
                {"_id": "emp1", "fullName": "Alice", "totalHours": 40.0}
            ]
            result = get_attendance_summary("month")
            assert "report" in result
            assert "raw" in result
```

**Step 2: Run test to verify failure**

```bash
python3 -m pytest tests/test_attendance_agent.py -v
```
Expected: FAIL — module not found / functions not defined.

**Step 3: Write `attendance_agent.py`**

```python
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
```

**Step 4: Run tests**

```bash
python3 -m pytest tests/test_attendance_agent.py -v
```
Expected: PASS

**Step 5: Commit**

```bash
git add attendance_agent.py tests/test_attendance_agent.py
git commit -m "feat: add attendance agent with timelog report and summary"
```

---

### Task 2: Funds Agent — Module

**Files:**
- Create: `funds_agent.py`
- Create: `tests/test_funds_agent.py`

**Step 1: Write failing tests**

```python
import pytest
from unittest.mock import patch, MagicMock
from funds_agent import get_funds_overview, get_petty_cash_status, get_advance_summary

class TestFundsAgent:
    def test_funds_overview_returns_structure(self):
        with patch("funds_agent.get_db") as mock_db, \
             patch("funds_agent.execute_pipeline") as mock_exec:
            mock_db.return_value = MagicMock()
            mock_exec.return_value = [{"name": "Petty Cash Office", "fundAmount": 3000.0, "currentBalance": 1500.0}]
            result = get_funds_overview()
            assert "report" in result
            assert "collection" in result

    def test_funds_overview_empty(self):
        with patch("funds_agent.get_db") as mock_db, \
             patch("funds_agent.execute_pipeline") as mock_exec:
            mock_db.return_value = MagicMock()
            mock_exec.return_value = []
            result = get_funds_overview()
            assert "No funds" in result["report"] or "no" in result["report"].lower()

    def test_petty_cash_status_returns_structure(self):
        with patch("funds_agent.get_db") as mock_db, \
             patch("funds_agent.execute_pipeline") as mock_exec:
            mock_db.return_value = MagicMock()
            mock_exec.side_effect = [[{"name": "Petty Cash Office", "fundAmount": 3000.0, "currentBalance": 1500.0}], [], []]
            result = get_petty_cash_status()
            assert "report" in result

    def test_advance_summary_returns_structure(self):
        with patch("funds_agent.get_db") as mock_db, \
             patch("funds_agent.execute_pipeline") as mock_exec:
            mock_db.return_value = MagicMock()
            mock_exec.return_value = [{"_id": "emp1", "fullName": "Alice", "totalOutstanding": 5000.0}]
            result = get_advance_summary()
            assert "report" in result
```

**Step 2: Run test to verify failure**

```bash
python3 -m pytest tests/test_funds_agent.py -v
```
Expected: FAIL — module not found.

**Step 3: Write `funds_agent.py`**

```python
from db import get_db, execute_pipeline

def _petty_cash_pipeline() -> list:
    return [
        {"$match": {"status": "ACTIVE"}},
        {"$project": {
            "name": 1,
            "fundAmount": 1,
            "currentBalance": 1,
            "utilization": {
                "$round": [{"$multiply": [{"$subtract": [1, {"$divide": ["$currentBalance", "$fundAmount"]}]}, 100]}, 1]
            },
        }},
    ]

def _advance_pipeline() -> list:
    return [
        {"$match": {"status": "ACTIVE"}},
        {"$group": {
            "_id": "$employeeId",
            "totalOutstanding": {"$sum": "$remainingBalance"},
            "advanceCount": {"$sum": 1},
        }},
        {"$lookup": {
            "from": "employees",
            "localField": "_id",
            "foreignField": "_id",
            "as": "employee",
        }},
        {"$unwind": {"path": "$employee", "preserveNullAndEmptyArrays": True}},
        {"$project": {
            "_id": 0,
            "employeeName": "$employee.fullName",
            "totalOutstanding": {"$round": ["$totalOutstanding", 2]},
            "advanceCount": 1,
        }},
        {"$sort": {"totalOutstanding": -1}},
    ]

def _account_balance_pipeline() -> list:
    return [
        {"$lookup": {
            "from": "accounts",
            "localField": "accountId",
            "foreignField": "_id",
            "as": "account",
        }},
        {"$unwind": {"path": "$account", "preserveNullAndEmptyArrays": True}},
        {"$group": {
            "_id": "$account.type",
            "totalDebit": {"$sum": "$debit"},
            "totalCredit": {"$sum": "$credit"},
        }},
        {"$project": {
            "accountType": "$_id",
            "totalDebit": {"$round": ["$totalDebit", 2]},
            "totalCredit": {"$round": ["$totalCredit", 2]},
            "netBalance": {"$round": [{"$subtract": ["$totalDebit", "$totalCredit"]}, 2]},
        }},
    ]

def _format_funds_report(petty_cash, advances, account_balances) -> str:
    lines = ["=== FUNDS OVERVIEW ===\n"]
    lines.append("--- Petty Cash ---")
    if petty_cash:
        for f in petty_cash:
            lines.append(f"  {f['name']}: Php {f['currentBalance']:,.2f} / Php {f['fundAmount']:,.2f} ({f['utilization']}% utilized)")
    else:
        lines.append("  No active petty cash funds.")

    lines.append("\n--- Employee Advances (Active) ---")
    if advances:
        for a in advances:
            lines.append(f"  {a['employeeName']}: Php {a['totalOutstanding']:,.2f} ({a['advanceCount']} advance(s))")
    else:
        lines.append("  No active advances.")

    lines.append("\n--- Account Balances ---")
    if account_balances:
        for a in account_balances:
            lines.append(f"  {a['accountType']}: Debit {a['totalDebit']:,.2f} | Credit {a['totalCredit']:,.2f} | Net {a['netBalance']:,.2f}")
    else:
        lines.append("  No account balances found.")
    return "\n".join(lines)

def get_funds_overview() -> dict:
    db = get_db()
    petty_cash = execute_pipeline(db, "petty_cash", _petty_cash_pipeline())
    advances = execute_pipeline(db, "advances", _advance_pipeline())
    account_balances = execute_pipeline(db, "journal_lines", _account_balance_pipeline())
    report = _format_funds_report(petty_cash, advances, account_balances)
    return {"report": report, "raw": {"petty_cash": petty_cash, "advances": advances, "accounts": account_balances}, "collection": "multiple", "pipeline": []}

def get_petty_cash_status(name: str = None) -> dict:
    pipeline = _petty_cash_pipeline()
    if name:
        pipeline.insert(0, {"$match": {"name": {"$regex": name, "$options": "i"}}})
    db = get_db()
    results = execute_pipeline(db, "petty_cash", pipeline)
    if not results:
        return {"report": "No petty cash funds found.", "raw": [], "collection": "petty_cash", "pipeline": pipeline}
    lines = ["Petty Cash Status:"]
    for f in results:
        lines.append(f"  {f['name']}: Php {f['currentBalance']:,.2f} / Php {f['fundAmount']:,.2f} ({f['utilization']}% utilized)")
    return {"report": "\n".join(lines), "raw": results, "collection": "petty_cash", "pipeline": pipeline}

def get_advance_summary() -> dict:
    db = get_db()
    results = execute_pipeline(db, "advances", _advance_pipeline())
    if not results:
        return {"report": "No active advances found.", "raw": [], "collection": "advances", "pipeline": []}
    lines = ["Active Employee Advances:"]
    total = 0
    for a in results:
        lines.append(f"  {a['employeeName']}: Php {a['totalOutstanding']:,.2f}")
        total += a['totalOutstanding']
    lines.append(f"\n  Total Outstanding: Php {total:,.2f}")
    return {"report": "\n".join(lines), "raw": results, "collection": "advances", "pipeline": []}
```

**Step 4: Run tests**

```bash
python3 -m pytest tests/test_funds_agent.py -v
```
Expected: PASS

**Step 5: Commit**

```bash
git add funds_agent.py tests/test_funds_agent.py
git commit -m "feat: add funds agent with petty cash, advances, account balances"
```

---

### Task 3: Balance Sheet Agent — Module

**Files:**
- Create: `balance_sheet_agent.py`
- Create: `tests/test_balance_sheet_agent.py`

**Step 1: Write failing tests**

```python
import pytest
from unittest.mock import patch, MagicMock
from balance_sheet_agent import check_balance, check_debits_equal_credits, check_assets_equals_liabilities_equity, find_unbalanced_entries

class TestBalanceSheetAgent:
    def test_check_debits_equal_credits_balanced(self):
        with patch("balance_sheet_agent.get_db") as mock_db, \
             patch("balance_sheet_agent.execute_pipeline") as mock_exec:
            mock_db.return_value = MagicMock()
            mock_exec.return_value = [{"totalDebit": 10000.0, "totalCredit": 10000.0, "variance": 0.0}]
            result = check_debits_equal_credits()
            assert "balanced" in result["report"].lower() or "PASS" in result["report"]

    def test_check_debits_equal_credits_unbalanced(self):
        with patch("balance_sheet_agent.get_db") as mock_db, \
             patch("balance_sheet_agent.execute_pipeline") as mock_exec:
            mock_db.return_value = MagicMock()
            mock_exec.return_value = [{"totalDebit": 10000.0, "totalCredit": 9500.0, "variance": 500.0}]
            result = check_debits_equal_credits()
            assert "FAIL" in result["report"] or "variance" in result["report"].lower()

    def test_assets_equals_liabilities_equity(self):
        with patch("balance_sheet_agent.get_db") as mock_db, \
             patch("balance_sheet_agent.execute_pipeline") as mock_exec:
            mock_db.return_value = MagicMock()
            mock_exec.side_effect = [
                [{"_id": "ASSET", "netBalance": 50000.0}, {"_id": "LIABILITY", "netBalance": 30000.0}, {"_id": "EQUITY", "netBalance": 20000.0}]
            ]
            result = check_assets_equals_liabilities_equity()
            assert "PASS" in result["report"] or "balanced" in result["report"].lower()

    def test_assets_equals_liabilities_equity_unbalanced(self):
        with patch("balance_sheet_agent.get_db") as mock_db, \
             patch("balance_sheet_agent.execute_pipeline") as mock_exec:
            mock_db.return_value = MagicMock()
            mock_exec.side_effect = [
                [{"_id": "ASSET", "netBalance": 50000.0}, {"_id": "LIABILITY", "netBalance": 20000.0}, {"_id": "EQUITY", "netBalance": 20000.0}]
            ]
            result = check_assets_equals_liabilities_equity()
            assert "FAIL" in result["report"] or "gap" in result["report"].lower()

    def test_find_unbalanced_entries_returns_list(self):
        with patch("balance_sheet_agent.get_db") as mock_db, \
             patch("balance_sheet_agent.execute_pipeline") as mock_exec:
            mock_db.return_value = MagicMock()
            mock_exec.return_value = [{"entryId": "abc", "totalDebit": 100.0, "totalCredit": 90.0}]
            result = find_unbalanced_entries()
            assert "raw" in result

    def test_check_balance_returns_all_checks(self):
        with patch("balance_sheet_agent.get_db") as mock_db, \
             patch("balance_sheet_agent.execute_pipeline") as mock_exec:
            mock_db.return_value = MagicMock()
            mock_exec.side_effect = [
                [{"totalDebit": 10000.0, "totalCredit": 10000.0, "variance": 0.0}],
                [{"_id": "ASSET", "netBalance": 50000.0}, {"_id": "LIABILITY", "netBalance": 30000.0}, {"_id": "EQUITY", "netBalance": 20000.0}],
                [],
            ]
            result = check_balance()
            assert "DEBITS = CREDITS" in result["report"]
            assert "A = L + E" in result["report"]
```

**Step 2: Run test to verify failure**

```bash
python3 -m pytest tests/test_balance_sheet_agent.py -v
```
Expected: FAIL — module not found.

**Step 3: Write `balance_sheet_agent.py`**

```python
from db import get_db, execute_pipeline

def _debits_equal_credits_pipeline() -> list:
    return [
        {"$group": {
            "_id": None,
            "totalDebit": {"$sum": "$debit"},
            "totalCredit": {"$sum": "$credit"},
        }},
        {"$project": {
            "_id": 0,
            "totalDebit": {"$round": ["$totalDebit", 2]},
            "totalCredit": {"$round": ["$totalCredit", 2]},
            "variance": {"$round": [{"$subtract": ["$totalDebit", "$totalCredit"]}, 2]},
            "balanced": {"$eq": [{"$subtract": ["$totalDebit", "$totalCredit"]}, 0]},
        }},
    ]

def _assets_liabilities_equity_pipeline() -> list:
    return [
        {"$lookup": {
            "from": "accounts",
            "localField": "accountId",
            "foreignField": "_id",
            "as": "account",
        }},
        {"$unwind": {"path": "$account", "preserveNullAndEmptyArrays": False}},
        {"$group": {
            "_id": "$account.type",
            "totalDebit": {"$sum": "$debit"},
            "totalCredit": {"$sum": "$credit"},
        }},
        {"$project": {
            "_id": 1,
            "netBalance": {"$round": [{"$subtract": ["$totalDebit", "$totalCredit"]}, 2]},
        }},
    ]

def _unbalanced_entries_pipeline() -> list:
    return [
        {"$group": {
            "_id": "$entryId",
            "totalDebit": {"$sum": "$debit"},
            "totalCredit": {"$sum": "$credit"},
        }},
        {"$match": {"$expr": {"$ne": ["$totalDebit", "$totalCredit"]}}},
        {"$lookup": {
            "from": "journal_entries",
            "localField": "_id",
            "foreignField": "_id",
            "as": "entry",
        }},
        {"$unwind": {"path": "$entry", "preserveNullAndEmptyArrays": True}},
        {"$project": {
            "_id": 0,
            "entryId": "$_id",
            "date": "$entry.date",
            "description": "$entry.description",
            "reference": "$entry.reference",
            "totalDebit": {"$round": ["$totalDebit", 2]},
            "totalCredit": {"$round": ["$totalCredit", 2]},
            "variance": {"$round": [{"$subtract": ["$totalDebit", "$totalCredit"]}, 2]},
        }},
    ]

def check_debits_equal_credits() -> dict:
    db = get_db()
    results = execute_pipeline(db, "journal_lines", _debits_equal_credits_pipeline())
    if not results:
        return {"report": "No journal line entries found.", "raw": [], "collection": "journal_lines", "pipeline": []}
    r = results[0]
    if r["balanced"]:
        report = f"PASS: Total Debits (Php {r['totalDebit']:,.2f}) = Total Credits (Php {r['totalCredit']:,.2f})"
    else:
        report = f"FAIL: Variance of Php {r['variance']:,.2f} — Debits (Php {r['totalDebit']:,.2f}) != Credits (Php {r['totalCredit']:,.2f})"
    return {"report": report, "raw": results, "collection": "journal_lines", "pipeline": []}

def check_assets_equals_liabilities_equity() -> dict:
    db = get_db()
    results = execute_pipeline(db, "journal_lines", _assets_liabilities_equity_pipeline())
    if not results:
        return {"report": "No account balances found.", "raw": [], "collection": "journal_lines", "pipeline": []}
    assets = 0
    liabilities = 0
    equity = 0
    for r in results:
        t = r["_id"]
        nb = r["netBalance"]
        if t == "ASSET":
            assets = nb
        elif t == "LIABILITY":
            liabilities = nb
        elif t == "EQUITY":
            equity = nb
    gap = abs(assets - (liabilities + equity))
    lines = [f"  Assets (A):      Php {assets:,.2f}", f"  Liabilities (L): Php {liabilities:,.2f}", f"  Equity (E):      Php {equity:,.2f}"]
    if gap < 0.01:
        lines.insert(0, f"PASS: A = L + E (Php {assets:,.2f} = Php {liabilities + equity:,.2f})")
    else:
        lines.insert(0, f"FAIL: Gap of Php {gap:,.2f} — A ({assets:,.2f}) != L + E ({liabilities + equity:,.2f})")
    return {"report": "\n".join(lines), "raw": results, "collection": "journal_lines", "pipeline": []}

def find_unbalanced_entries() -> dict:
    db = get_db()
    results = execute_pipeline(db, "journal_lines", _unbalanced_entries_pipeline())
    if not results:
        return {"report": "All journal entries are balanced.", "raw": [], "collection": "journal_lines", "pipeline": []}
    lines = [f"Found {len(results)} unbalanced entr(ies):"]
    for r in results:
        lines.append(f"  {r.get('reference', 'N/A')} ({r.get('date', 'N/A')}): Debit {r['totalDebit']:,.2f} / Credit {r['totalCredit']:,.2f} (var {r['variance']:,.2f})")
    return {"report": "\n".join(lines), "raw": results, "collection": "journal_lines", "pipeline": []}

def check_balance() -> dict:
    dc = check_debits_equal_credits()
    ale = check_assets_equals_liabilities_equity()
    ue = find_unbalanced_entries()
    report = f"<<< BALANCE SHEET VERIFICATION >>>\n\n--- Check 1: Debits = Credits ---\n{dc['report']}\n\n--- Check 2: Assets = Liabilities + Equity ---\n{ale['report']}\n\n--- Check 3: Unbalanced Entries ---\n{ue['report']}"
    return {"report": report, "raw": dc["raw"] + ale["raw"] + ue["raw"], "collection": "journal_lines", "pipeline": []}
```

**Step 4: Run tests**

```bash
python3 -m pytest tests/test_balance_sheet_agent.py -v
```
Expected: PASS

**Step 5: Commit**

```bash
git add balance_sheet_agent.py tests/test_balance_sheet_agent.py
git commit -m "feat: add balance sheet agent with debit/credit and A=L+E checks"
```

---

### Task 4: Agent Router — Modify `agent.py`

**Files:**
- Modify: `agent.py` (add import + command routing at top of `run_query`)

**Step 1: Write failing test in `tests/test_agent.py`**

Add to existing `tests/test_agent.py`:

```python
def test_run_query_routes_attendance_command(self):
    with patch("agent.get_db") as mock_db, \
         patch("agent.introspect_schema") as mock_schema:
        mock_db.return_value = MagicMock()
        mock_schema.return_value = {"database": "test", "collections": {}, "collection_names": ["timelogs"]}
        result = run_query("/attendance today")
        assert "report" in result
        assert result["collection"] == "timelogs"
```

**Step 2: Run test to verify failure**

```bash
python3 -m pytest tests/test_agent.py::TestAgentEngine::test_run_query_routes_attendance_command -v
```
Expected: FAIL — `/attendance` not routed, falls through to LLM path.

**Step 3: Modify `agent.py`**

```python
import json
from db import get_db, introspect_schema, execute_pipeline
from llm import generate_pipeline, interpret_results, select_collection
from attendance_agent import get_attendance_report, get_attendance_summary
from funds_agent import get_funds_overview, get_petty_cash_status, get_advance_summary
from balance_sheet_agent import check_balance, check_debits_equal_credits, check_assets_equals_liabilities_equity, find_unbalanced_entries

MAX_RETRIES = 2

def _parse_command(query: str) -> dict:
    q = query.strip().lower()
    parts = q.split(maxsplit=2)
    cmd = parts[0] if parts else ""
    args = parts[1:] if len(parts) > 1 else []
    return {"command": cmd, "args": args, "raw": query}

def run_query(query: str, target_collection: str = None) -> dict:
    cmd = _parse_command(query)
    
    # Automation command routing
    if cmd["command"] == "/attendance":
        period = cmd["args"][0] if cmd["args"] else "today"
        employee = cmd["args"][1] if len(cmd["args"]) > 1 else None
        if period == "summary":
            return get_attendance_summary(cmd["args"][1] if len(cmd["args"]) > 1 else "month")
        return get_attendance_report(period, employee)
    
    if cmd["command"] == "/funds":
        sub = cmd["args"][0] if cmd["args"] else "all"
        if sub == "petty":
            return get_petty_cash_status(" ".join(cmd["args"][1:]) if len(cmd["args"]) > 1 else None)
        if sub == "advances":
            return get_advance_summary()
        return get_funds_overview()
    
    if cmd["command"] == "/balance":
        sub = cmd["args"][0] if cmd["args"] else "all"
        if sub == "debits":
            return check_debits_equal_credits()
        if sub == "entries":
            return find_unbalanced_entries()
        if sub == "equation":
            return check_assets_equals_liabilities_equity()
        return check_balance()
    
    # Fall through to existing LLM flow (unchanged)
    db = get_db()
    schema = introspect_schema(db)
    ...
```

**Step 4: Run tests**

```bash
python3 -m pytest tests/test_agent.py -v
```
Expected: PASS (all existing + new tests)

**Step 5: Commit**

```bash
git add agent.py
git commit -m "feat: add automation command routing to agent"
```

---

### Task 5: Main CLI — Handle `/commands` in one-shot mode

**Files:**
- Modify: `main.py` (click command skips LLM provider setup for automation commands)

**Step 1: Write failing test in `tests/test_main.py`**

(Check if test_main.py exists — read it first. If not, create it.)

**Step 2: Verify current behavior**

```bash
python3 main.py "/attendance today"
```
Expected: Should error on missing DB or route to agent.

**Step 3: Modify `main.py`**

```python
# In main() function, before interactive_mode check, add:
@click.command()
@click.argument("query", required=False)
@click.option("--collection", "-c", help="Target collection")
@click.option("--raw", is_flag=True, help="Show raw data table")
def main(query, collection, raw):
    if not query:
        interactive_mode()
        return

    from agent import run_query
    from formatter import print_report, print_error

    try:
        result = run_query(query, target_collection=collection)
        print_report(result["report"], result.get("raw"), show_raw=raw, collection=result.get("collection"))
    except Exception as e:
        print_error(str(e))
        sys.exit(1)
```
(This is already correct — no changes needed. The agent router handles it.)

**Step 4: Smoke test**

```bash
python3 -m pytest tests/ -v --ignore=tests/test_integration.py
```
Expected: All pass.

**Step 5: Commit**

```bash
git add main.py
git commit -m "chore: ensure automation commands work in one-shot mode"
```
(If no actual changes to main.py, skip commit.)

---

### Task 6: Full Test Suite Pass

**Step 1: Run all unit tests**

```bash
python3 -m pytest tests/ -v --ignore=tests/test_integration.py
```
Expected: All tests pass.

**Step 2: Verify no regressions**

```bash
python3 -m pytest tests/ --tb=short --ignore=tests/test_integration.py
```
Expected: 0 failures.

**Step 3: Commit the planetest suite pass**

```bash
git add -A
git commit -m "chore: full test suite pass for automation agents"
```
