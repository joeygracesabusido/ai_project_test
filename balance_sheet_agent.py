from db import get_db, execute_pipeline
from pymongo.errors import ConnectionFailure


def _debits_equal_credits_pipeline() -> list:
    return [
        {"$group": {
            "_id": None,
            "totalDebit": {"$sum": "$debit"},
            "totalCredit": {"$sum": "$credit"}
        }},
        {"$project": {
            "_id": 0,
            "totalDebit": {"$round": ["$totalDebit", 2]},
            "totalCredit": {"$round": ["$totalCredit", 2]},
            "variance": {"$round": [{"$subtract": ["$totalDebit", "$totalCredit"]}, 2]},
            "balanced": {"$eq": [
                {"$round": [{"$subtract": ["$totalDebit", "$totalCredit"]}, 2]},
                0
            ]}
        }}
    ]


def _assets_liabilities_equity_pipeline() -> list:
    return [
        {"$lookup": {
            "from": "accounts",
            "localField": "accountId",
            "foreignField": "_id",
            "as": "account"
        }},
        {"$unwind": {"path": "$account", "preserveNullAndEmptyArrays": False}},
        {"$group": {
            "_id": "$account.type",
            "totalDebit": {"$sum": "$debit"},
            "totalCredit": {"$sum": "$credit"}
        }},
        {"$project": {
            "_id": 0,
            "accountType": "$_id",
            "netBalance": {"$round": [{"$subtract": ["$totalDebit", "$totalCredit"]}, 2]}
        }}
    ]


def _unbalanced_entries_pipeline() -> list:
    return [
        {"$group": {
            "_id": "$entryId",
            "totalDebit": {"$sum": "$debit"},
            "totalCredit": {"$sum": "$credit"}
        }},
        {"$match": {"$expr": {"$ne": ["$totalDebit", "$totalCredit"]}}},
        {"$lookup": {
            "from": "journal_entries",
            "localField": "_id",
            "foreignField": "_id",
            "as": "entry"
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
            "variance": {"$round": [{"$subtract": ["$totalDebit", "$totalCredit"]}, 2]}
        }}
    ]


def check_debits_equal_credits() -> dict:
    pipeline = _debits_equal_credits_pipeline()
    try:
        db = get_db()
        results = execute_pipeline(db, "journal_lines", pipeline)
    except (ValueError, ConnectionFailure) as e:
        return {"report": f"Database error: {e}", "raw": [], "collection": "journal_lines", "pipeline": pipeline}
    if not results:
        return {"report": "No journal line entries found.", "raw": [], "collection": "journal_lines", "pipeline": pipeline}
    result = results[0]
    total_debit = result.get("totalDebit", 0)
    total_credit = result.get("totalCredit", 0)
    variance = result.get("variance", 0)
    if result.get("balanced", False):
        return {"report": f"PASS: Total Debits (Php {total_debit:.2f}) = Total Credits (Php {total_credit:.2f})", "raw": results, "collection": "journal_lines", "pipeline": pipeline}
    return {"report": f"FAIL: Variance of Php {variance:.2f} — Debits (Php {total_debit:.2f}) != Credits (Php {total_credit:.2f})", "raw": results, "collection": "journal_lines", "pipeline": pipeline}


def check_assets_equals_liabilities_equity() -> dict:
    pipeline = _assets_liabilities_equity_pipeline()
    try:
        db = get_db()
        results = execute_pipeline(db, "journal_lines", pipeline)
    except (ValueError, ConnectionFailure) as e:
        return {"report": f"Database error: {e}", "raw": [], "collection": "journal_lines", "pipeline": pipeline}
    if not results:
        return {"report": "No account balances found.", "raw": [], "collection": "journal_lines", "pipeline": pipeline}
    assets = 0.0
    liabilities = 0.0
    equity = 0.0
    for r in results:
        acct_type = r.get("accountType", "")
        net = r.get("netBalance", 0)
        if acct_type == "ASSET":
            assets = net
        elif acct_type == "LIABILITY":
            liabilities = net
        elif acct_type == "EQUITY":
            equity = net
    gap = abs(assets - (liabilities + equity))
    if gap < 0.01:
        return {"report": f"PASS: A = L + E (Php {assets:.2f} = Php {liabilities + equity:.2f})", "raw": results, "collection": "journal_lines", "pipeline": pipeline}
    return {"report": f"FAIL: Gap of Php {gap:.2f} — A ({assets:.2f}) != L + E ({liabilities + equity:.2f})", "raw": results, "collection": "journal_lines", "pipeline": pipeline}


def find_unbalanced_entries() -> dict:
    pipeline = _unbalanced_entries_pipeline()
    try:
        db = get_db()
        results = execute_pipeline(db, "journal_lines", pipeline)
    except (ValueError, ConnectionFailure) as e:
        return {"report": f"Database error: {e}", "raw": [], "collection": "journal_lines", "pipeline": pipeline}
    if not results:
        return {"report": "All journal entries are balanced.", "raw": [], "collection": "journal_lines", "pipeline": pipeline}
    lines = ["Unbalanced Entries:"]
    for r in results:
        ref = r.get("reference", "N/A")
        date = r.get("date", "N/A")
        debit = r.get("totalDebit", 0)
        credit = r.get("totalCredit", 0)
        variance = r.get("variance", 0)
        desc = r.get("description", "")
        lines.append(f"  {ref} ({date}): Debits Php {debit:.2f} / Credits Php {credit:.2f} (Variance: Php {variance:.2f}) {desc}")
    return {"report": "\n".join(lines), "raw": results, "collection": "journal_lines", "pipeline": pipeline}


def check_balance() -> dict:
    debits_check = check_debits_equal_credits()
    ale_check = check_assets_equals_liabilities_equity()
    unbalanced_check = find_unbalanced_entries()
    parts = [
        "=== DEBITS = CREDITS ===",
        debits_check.get("report", ""),
        "",
        "=== A = L + E ===",
        ale_check.get("report", ""),
        "",
        "=== UNBALANCED ENTRIES ===",
        unbalanced_check.get("report", ""),
    ]
    combined_report = "\n".join(parts)
    combined_raw = {
        "debits_equal_credits": debits_check.get("raw", []),
        "assets_equals_liabilities_equity": ale_check.get("raw", []),
        "unbalanced_entries": unbalanced_check.get("raw", []),
    }
    return {
        "report": combined_report,
        "raw": combined_raw,
        "collection": "journal_lines",
        "pipeline": None,
    }
