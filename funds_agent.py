from db import get_db, execute_pipeline
from pymongo.errors import ConnectionFailure


def _petty_cash_pipeline() -> list:
    return [
        {"$match": {"status": "ACTIVE"}},
        {"$project": {
            "name": 1,
            "fundAmount": 1,
            "currentBalance": 1,
            "utilization": {
                "$round": [
                    {"$multiply": [
                        {"$subtract": [1, {"$divide": ["$currentBalance", "$fundAmount"]}]},
                        100
                    ]},
                    1
                ]
            }
        }}
    ]


def _advance_pipeline() -> list:
    return [
        {"$match": {"status": "ACTIVE"}},
        {"$group": {
            "_id": "$employeeId",
            "totalRemaining": {"$sum": "$remainingBalance"},
            "count": {"$sum": 1}
        }},
        {"$lookup": {
            "from": "employees",
            "localField": "_id",
            "foreignField": "_id",
            "as": "employee"
        }},
        {"$unwind": {"path": "$employee", "preserveNullAndEmptyArrays": True}},
        {"$project": {
            "employeeName": {"$ifNull": ["$employee.fullName", "Unknown"]},
            "totalOutstanding": {"$round": ["$totalRemaining", 2]},
            "advanceCount": "$count"
        }},
        {"$sort": {"totalOutstanding": -1}}
    ]


def _account_balance_pipeline() -> list:
    return [
        {"$lookup": {
            "from": "accounts",
            "localField": "accountId",
            "foreignField": "_id",
            "as": "account"
        }},
        {"$unwind": {"path": "$account", "preserveNullAndEmptyArrays": True}},
        {"$group": {
            "_id": "$account.type",
            "totalDebit": {"$sum": "$debit"},
            "totalCredit": {"$sum": "$credit"}
        }},
        {"$project": {
            "accountType": "$_id",
            "totalDebit": {"$round": ["$totalDebit", 2]},
            "totalCredit": {"$round": ["$totalCredit", 2]},
            "netBalance": {"$round": [{"$subtract": ["$totalDebit", "$totalCredit"]}, 2]}
        }}
    ]


def _format_funds_report(petty_cash: list, advances: list, account_balances: list) -> str:
    lines = []
    lines.append("Petty Cash:")
    if petty_cash:
        for f in petty_cash:
            name = f.get("name", "Unknown")
            fund = f.get("fundAmount", 0)
            balance = f.get("currentBalance", 0)
            util = f.get("utilization", 0)
            lines.append(f"  {name}: Php{balance:.2f} / Php{fund:.2f} ({util}%)")
    else:
        lines.append("  No active petty cash funds.")
    lines.append("")
    lines.append("Employee Advances:")
    if advances:
        for a in advances:
            name = a.get("employeeName", "Unknown")
            outstanding = a.get("totalOutstanding", 0)
            count = a.get("advanceCount", 0)
            lines.append(f"  {name}: Php{outstanding:.2f} ({count} advance(s))")
    else:
        lines.append("  No active advances.")
    lines.append("")
    lines.append("Account Balances:")
    if account_balances:
        for b in account_balances:
            acct_type = b.get("accountType", "Unknown")
            debit = b.get("totalDebit", 0)
            credit = b.get("totalCredit", 0)
            net = b.get("netBalance", 0)
            lines.append(f"  {acct_type}: Debits Php{debit:.2f} / Credits Php{credit:.2f} (Net: Php{net:.2f})")
    else:
        lines.append("  No account balances found.")
    return "\n".join(lines)


def get_funds_overview() -> dict:
    try:
        db = get_db()
        petty_cash = execute_pipeline(db, "petty_cash", _petty_cash_pipeline())
        advances = execute_pipeline(db, "advances", _advance_pipeline())
        account_balances = execute_pipeline(db, "journal_lines", _account_balance_pipeline())
    except (ValueError, ConnectionFailure) as e:
        return {"report": f"Database error: {e}", "raw": {}, "collection": "funds", "pipeline": None}
    report = _format_funds_report(petty_cash, advances, account_balances)
    return {
        "report": report,
        "raw": {
            "petty_cash": petty_cash,
            "advances": advances,
            "account_balances": account_balances
        },
        "collection": "funds",
        "pipeline": {
            "petty_cash": _petty_cash_pipeline(),
            "advances": _advance_pipeline(),
            "account_balances": _account_balance_pipeline()
        }
    }


def get_petty_cash_status(name: str = None) -> dict:
    pipeline = _petty_cash_pipeline()
    if name:
        pipeline.insert(1, {"$match": {"name": name}})
    try:
        db = get_db()
        results = execute_pipeline(db, "petty_cash", pipeline)
    except (ValueError, ConnectionFailure) as e:
        return {"report": f"Database error: {e}", "raw": [], "collection": "petty_cash", "pipeline": pipeline}
    if not results:
        msg = f"Petty cash fund '{name}' not found." if name else "No petty cash funds found."
        return {"report": msg, "raw": [], "collection": "petty_cash", "pipeline": pipeline}
    lines = ["Petty Cash Status:"]
    for r in results:
        lines.append(f"  {r.get('name', 'Unknown')}: Php{r.get('currentBalance', 0):.2f} / Php{r.get('fundAmount', 0):.2f} ({r.get('utilization', 0)}% utilized)")
    return {"report": "\n".join(lines), "raw": results, "collection": "petty_cash", "pipeline": pipeline}


def get_advance_summary() -> dict:
    pipeline = _advance_pipeline()
    try:
        db = get_db()
        results = execute_pipeline(db, "advances", pipeline)
    except (ValueError, ConnectionFailure) as e:
        return {"report": f"Database error: {e}", "raw": [], "collection": "advances", "pipeline": pipeline}
    if not results:
        return {"report": "No active advances found.", "raw": [], "collection": "advances", "pipeline": pipeline}
    total = sum(r.get("totalOutstanding", 0) for r in results)
    lines = ["Employee Advances:"]
    for r in results:
        lines.append(f"  {r.get('employeeName', 'Unknown')}: Php{r.get('totalOutstanding', 0):.2f} ({r.get('advanceCount', 0)} advance(s))")
    lines.append(f"  Total Outstanding: Php{total:.2f}")
    return {"report": "\n".join(lines), "raw": results, "collection": "advances", "pipeline": pipeline}
