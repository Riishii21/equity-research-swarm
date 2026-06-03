"""Live fetchers for multi-year financials, ratios, and peer comps (read-only).
Field names verified against FMP /stable responses.
"""
from __future__ import annotations

from ..config import CONFIG
from .live_metrics import _get_json, LiveDataError

_BASE = "https://financialmodelingprep.com/stable"


def fetch_financial_history(ticker: str, years: int = 5) -> list[dict]:
    key = CONFIG.fmp_api_key
    if not key:
        raise LiveDataError("FMP_API_KEY not set")
    data = _get_json(f"{_BASE}/income-statement?symbol={ticker}&limit={years}&apikey={key}")
    if isinstance(data, dict) and data.get("Error Message"):
        raise LiveDataError(f"FMP: {data['Error Message']}")
    if not isinstance(data, list) or not data:
        raise LiveDataError(f"No financial history for {ticker}")
    out = []
    for r in data:
        out.append({
            "fiscal_year": r.get("fiscalYear") or (r.get("date", "")[:4]),
            "revenue": r.get("revenue"),
            "net_income": r.get("netIncome"),
            "gross_profit": r.get("grossProfit"),
            "operating_income": r.get("operatingIncome"),
            "eps_diluted": r.get("epsDiluted"),
        })
    return out


def fetch_ratio_history(ticker: str, years: int = 5) -> list[dict]:
    key = CONFIG.fmp_api_key
    if not key:
        raise LiveDataError("FMP_API_KEY not set")
    data = _get_json(f"{_BASE}/ratios?symbol={ticker}&limit={years}&apikey={key}")
    if not isinstance(data, list) or not data:
        raise LiveDataError(f"No ratio history for {ticker}")
    out = []
    for r in data:
        out.append({
            "fiscal_year": r.get("fiscalYear") or (r.get("date", "")[:4]),
            "gross_margin": _pct(r.get("grossProfitMargin")),
            "operating_margin": _pct(r.get("operatingProfitMargin")),
            "net_margin": _pct(r.get("netProfitMargin")),
            "pe_ratio": r.get("priceToEarningsRatio"),
        })
    return out


def fetch_peers(ticker: str, top_n: int = 6) -> list[dict]:
    key = CONFIG.fmp_api_key
    if not key:
        raise LiveDataError("FMP_API_KEY not set")
    data = _get_json(f"{_BASE}/stock-peers?symbol={ticker}&apikey={key}")
    if not isinstance(data, list) or not data:
        raise LiveDataError(f"No peers for {ticker}")
    peers = []
    for p in data:
        mc = p.get("mktCap") or p.get("marketCap")
        if not mc:
            continue
        peers.append({
            "symbol": p.get("symbol"),
            "name": p.get("companyName", ""),
            "price": p.get("price"),
            "market_cap": mc,
        })
    peers.sort(key=lambda x: x["market_cap"], reverse=True)
    return peers[:top_n]


def _pct(v):
    if v is None:
        return None
    try:
        return round(float(v) * 100, 1)
    except (TypeError, ValueError):
        return None
    
def fetch_statements(ticker: str) -> dict:
    """Latest income, balance sheet, and cash flow statements as curated
    line-item lists (label, value). Analyst-relevant lines only, in order."""
    key = CONFIG.fmp_api_key
    if not key:
        raise LiveDataError("FMP_API_KEY not set")

    def _one(endpoint):
        d = _get_json(f"{_BASE}/{endpoint}?symbol={ticker}&limit=1&apikey={key}")
        if isinstance(d, dict) and d.get("Error Message"):
            raise LiveDataError(f"FMP: {d['Error Message']}")
        if not isinstance(d, list) or not d:
            return {}
        return d[0]

    inc = _one("income-statement")
    bal = _one("balance-sheet-statement")
    cf = _one("cash-flow-statement")

    def rows(src, spec):
        out = []
        for label, field in spec:
            v = src.get(field)
            if v is not None:
                out.append({"label": label, "value": v})
        return out

    period = inc.get("fiscalYear") or bal.get("fiscalYear") or ""
    return {
        "period": period,
        "income": rows(inc, [
            ("Revenue", "revenue"), ("Cost of revenue", "costOfRevenue"),
            ("Gross profit", "grossProfit"), ("Operating expenses", "operatingExpenses"),
            ("Operating income", "operatingIncome"), ("EBITDA", "ebitda"),
            ("Income before tax", "incomeBeforeTax"), ("Income tax", "incomeTaxExpense"),
            ("Net income", "netIncome"), ("Diluted EPS", "epsDiluted"),
        ]),
        "balance": rows(bal, [
            ("Cash & equivalents", "cashAndCashEquivalents"),
            ("Cash & short-term inv.", "cashAndShortTermInvestments"),
            ("Total current assets", "totalCurrentAssets"),
            ("Property, plant & equip.", "propertyPlantEquipmentNet"),
            ("Total assets", "totalAssets"),
            ("Total current liabilities", "totalCurrentLiabilities"),
            ("Short-term debt", "shortTermDebt"), ("Long-term debt", "longTermDebt"),
            ("Total liabilities", "totalLiabilities"),
            ("Total equity", "totalStockholdersEquity"),
            ("Total debt", "totalDebt"), ("Net debt", "netDebt"),
        ]),
        "cashflow": rows(cf, [
            ("Net income", "netIncome"),
            ("Depreciation & amort.", "depreciationAndAmortization"),
            ("Stock-based comp.", "stockBasedCompensation"),
            ("Change in working capital", "changeInWorkingCapital"),
            ("Operating cash flow", "netCashProvidedByOperatingActivities"),
            ("Capital expenditure", "capitalExpenditure"),
            ("Free cash flow", "freeCashFlow"),
            ("Investing cash flow", "netCashProvidedByInvestingActivities"),
            ("Financing cash flow", "netCashProvidedByFinancingActivities"),
            ("Dividends paid", "netDividendsPaid"),
            ("Share repurchases", "commonStockRepurchased"),
            ("Net change in cash", "netChangeInCash"),
        ]),
    }