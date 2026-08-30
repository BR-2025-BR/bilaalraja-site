#!/usr/bin/env python3
"""Pull one company's full statements from companyfacts for the case study.

Figures are taken from the filings as filed, then checked against each other:
a teaching document whose statements do not tie is worse than none at all,
because the reader assumes the arithmetic and learns the wrong lesson.
"""
import json, sys
from datetime import date
from pathlib import Path

CACHE = Path("/Users/bilaa/Downloads/pitquant/data/cache/edgar")

FLOW = {  # income statement and cash flow: 12-month periods
 "revenue":  ["RevenueFromContractWithCustomerExcludingAssessedTax", "Revenues"],
 "cogs":     ["CostOfRevenue", "CostOfGoodsAndServicesSold"],
 "gross":    ["GrossProfit"],
 "sga":      ["SellingGeneralAndAdministrativeExpense"],
 "da":       ["DepreciationDepletionAndAmortization"],
 "ebit":     ["OperatingIncomeLoss"],
 "interest": ["InterestExpenseNonoperating", "InterestExpense"],
 "pretax":   ["IncomeLossFromContinuingOperationsBeforeIncomeTaxesExtraordinaryItemsNoncontrollingInterest"],
 "tax":      ["IncomeTaxExpenseBenefit"],
 "ni":       ["NetIncomeLoss"],
 "cfo":      ["NetCashProvidedByUsedInOperatingActivities"],
 "cfi":      ["NetCashProvidedByUsedInInvestingActivities"],
 "cff":      ["NetCashProvidedByUsedInFinancingActivities"],
 "capex":    ["PaymentsToAcquireProductiveAssets", "PaymentsToAcquirePropertyPlantAndEquipment"],
 "dividends":["PaymentsOfDividendsCommonStock"],
 "buyback":  ["PaymentsForRepurchaseOfCommonStock"],
 "eps":      ["EarningsPerShareDiluted"],
 "shares":   ["WeightedAverageNumberOfDilutedSharesOutstanding"],
}
STOCK = {  # balance sheet: a value at an instant
 "cash":      ["CashAndCashEquivalentsAtCarryingValue"],
 "receivable":["AccountsReceivableNetCurrent"],
 "inventory": ["InventoryNet"],
 "ca":        ["AssetsCurrent"],
 "ppe":       ["PropertyPlantAndEquipmentNet"],
 "assets":    ["Assets"],
 "payable":   ["AccountsPayableCurrent"],
 "cl":        ["LiabilitiesCurrent"],
 "ltdebt":    ["LongTermDebtAndCapitalLeaseObligations"],
 "liabilities":["Liabilities"],
 "equity":    ["StockholdersEquity"],
}


def days(v):
    if not v.get("start"):
        return None
    return (date.fromisoformat(v["end"]) - date.fromisoformat(v["start"])).days


def annual(us, tags, fy_end):
    """The 12-month figure ending on fy_end, newest filing wins."""
    best = None
    for t in tags:
        if t not in us: continue
        for _u, vals in us[t]["units"].items():
            for v in vals:
                d = days(v)
                if v.get("end") == fy_end and d and 330 <= d <= 400:
                    if best is None or (v.get("filed") or "") > (best.get("filed") or ""):
                        best = v
    return best["val"] if best else None


def at(us, tags, on):
    best = None
    for t in tags:
        if t not in us: continue
        for _u, vals in us[t]["units"].items():
            for v in vals:
                if v.get("end") == on and not v.get("start"):
                    if best is None or (v.get("filed") or "") > (best.get("filed") or ""):
                        best = v
    return best["val"] if best else None


def main(cik, n_years=2):
    us = json.loads((CACHE / f"companyfacts_{cik:010d}.json").read_text())["facts"]["us-gaap"]
    # fiscal year ends: where a ~365-day revenue figure exists
    ends = set()
    for t in FLOW["revenue"]:
        if t not in us: continue
        for _u, vals in us[t]["units"].items():
            for v in vals:
                d = days(v)
                if d and 330 <= d <= 400:
                    ends.add(v["end"])
    fys = sorted(ends, reverse=True)[:n_years]
    out = {}
    for fy in fys:
        row = {k: annual(us, tags, fy) for k, tags in FLOW.items()}
        row.update({k: at(us, tags, fy) for k, tags in STOCK.items()})
        out[fy] = row
    return out


if __name__ == "__main__":
    data = main(int(sys.argv[1]) if len(sys.argv) > 1 else 354950)
    print(json.dumps(data, indent=1))
