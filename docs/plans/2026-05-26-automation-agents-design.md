# Automation Agents Design

> **Date:** 2026-05-26
> **Status:** Approved

## Overview

Three specialized automation agents that extend the existing MongoDB AI CLI with pre-built, domain-specific pipelines for attendance reporting, fund balance monitoring, and balance sheet verification.

## Architecture

```
main.py (CLI)
  └─ agent.py (orchestrator / intent router)
       ├─ attendance_agent.py  → pre-built pipelines for timelogs
       ├─ funds_agent.py       → pre-built pipelines for fund balances
       ├─ balance_sheet_agent.py → pre-built pipelines for balance checks
       └─ llm.py (fallback for generic queries)
```

Interactive commands:
- `/attendance [period] [employee]` — timelog report
- `/funds` — all fund balance overview
- `/balance [check]` — balance sheet verification

Each agent returns `{report, raw, collection, pipeline}` — same contract as `run_query()`, so `formatter.py` unchanged.

## 1. Attendance Agent (`attendance_agent.py`)

### What it does
Pre-built aggregation pipelines for timelog queries with date range and employee filters.

### Functions
- `get_attendance_report(period="today", employee=None)` — raw timelogs with employee details
- `get_attendance_summary(period="month")` — per-employee: total hours, late/undertime counts
- `_date_range(period)` — helper: "today" | "week" | "month" | "YYYY-MM-DD:YYYY-MM-DD" → (start, end)

### Pipeline: Attendance Report
```
$match: date >= start AND date <= end [AND employeeId]
$lookup: employees → fullName, department, position
$project: clockIn, clockOut, workHours, otHours, lateMinutes, undertimeMinutes, status flags
$sort: date ascending
```

### Pipeline: Attendance Summary
```
$match: date in range
$lookup: employees
$group: by employeeId → sum(workHours), sum(otHours), avg(lateMinutes), count(lateMinutes > 0)
$sort: totalWorkHours descending
```

### Interpretation
Builds a natural-language summary from the aggregated data. For the summary: "Employee X worked Y hours, was late Z times." For details: per-day table.

## 2. Funds Agent (`funds_agent.py`)

### What it does
Shows remaining balances across petty cash funds, employee advances, and account-level fund tracking.

### Functions
- `get_funds_overview()` — single report with all fund types
- `get_petty_cash_status(name=None)` — detail per petty cash fund
- `get_advance_summary()` — outstanding advances grouped by employee

### Pipeline: Funds Overview
Three independent sub-pipelines merged into one report:

**Petty Cash:**
```
$project: name, fundAmount, currentBalance, utilization = 1 - (currentBalance/fundAmount)
$match: status = ACTIVE
```

**Advances (active):**
```
$match: status = ACTIVE
$group: null → totalOutstanding = sum(remainingBalance), count
$lookup: employees
```

**Account Balances:**
```
$lookup: journal_lines → accounts by accountId
$group: by account type → sum(debit), sum(credit), net
```

### Interpretation
Structured table: Fund Name | Type | Allocated | Spent | Remaining | Utilization %
Separate section for: Petty Cash, Advances, Account Balances.

## 3. Balance Sheet Agent (`balance_sheet_agent.py`)

### What it does
Verifies accounting equation and double-entry integrity.

### Functions
- `check_balance()` — run all checks, return comprehensive report
- `check_debits_equal_credits()` — verify double-entry across all journal lines
- `check_assets_equals_liabilities_equity()` — verify A = L + E
- `find_unbalanced_entries()` — identify specific entries that don't balance

### Pipeline: Debits = Credits
```
$group: journal_lines → totalDebit = sum(debit), totalCredit = sum(credit)
$project: variance = totalDebit - totalCredit, balanced = variance == 0
```

### Pipeline: A = L + E
```
$lookup: journal_lines.accountId → accounts (type, normalBalance)
$group: by accounts.type → sum(debit), sum(credit)
$project: for ASSET → netDebit = debit - credit
          for LIABILITY → netCredit = credit - debit
          for EQUITY → netCredit = credit - debit
Verify: totalAssets == totalLiabilities + totalEquity
```

### Pipeline: Unbalanced Entries
```
$group: journal_lines by entryId → entryDebit = sum(debit), entryCredit = sum(credit)
$match: entryDebit != entryCredit
$lookup: journal_entries for date, description, reference
```

### Interpretation
Pass/Fail for each check with specific amounts. If unbalanced, list the offending entries with dates and amounts.

## 4. Integration in `agent.py`

```
run_query(query, target_collection):
    cmd = parse_command(query)  # check for /attendance, /funds, /balance
    if cmd:
        route to appropriate agent
        return {report, raw, collection, pipeline}
    # else: existing LLM-based flow
```

## 5. Modified Files

| File | Change |
|------|--------|
| `attendance_agent.py` | **Create** — attendance/timelog agent |
| `funds_agent.py` | **Create** — fund balance agent |
| `balance_sheet_agent.py` | **Create** — balance sheet agent |
| `agent.py` | **Modify** — add `/command` routing |
| `main.py` | **Modify** — ensure `/commands` work in interactive mode |
| `tests/test_attendance_agent.py` | **Create** — unit tests |
| `tests/test_funds_agent.py` | **Create** — unit tests |
| `tests/test_balance_sheet_agent.py` | **Create** — unit tests |

## 6. Testing Strategy

### Unit tests (mock `get_db`, mock `execute_pipeline`)
- Each agent function returns correct structure
- Date range parsing works for all formats
- Pipeline structure is valid MongoDB aggregation (verified by inspection)
- Empty data returns graceful message
- Invalid period returns error

### Integration tests (live DB, optional)
- `/attendance month "Employee Name"` returns real data
- `/funds` shows actual fund balances
- `/balance` verifies actual journal entries

## 7. Error Handling

| Error | Response |
|-------|----------|
| No timelogs for period | Show available date range from max/min |
| Invalid period format | Show valid formats: today, week, month, YYYY-MM-DD:YYYY-MM-DD |
| Employee not found | List matching employees |
| DB connection failure | Error message with diagnostics |
| Unbalanced entries found | List them with amounts, don't just warn |
