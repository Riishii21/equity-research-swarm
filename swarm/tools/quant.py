"""Read-only financial metric tools.

Least-privilege by design: every function only *reads*. There is deliberately
no tool that places trades, transfers funds, or mutates state — this is the
LLM06 'excessive agency' mitigation made concrete. In sample mode metrics come
from the bundled filing data; live mode would back these with yfinance.
"""
from __future__ import annotations
import json
from pathlib import Path
from ..config import CONFIG

_DATA = Path(__file__).resolve().parent.parent / "data" / "filings"

# In a real system these come from yfinance/EDGAR XBRL. Bundled here so the
# quant agent has tool results to ground claims on, offline.
_SAMPLE_METRICS = {
    "DEMO": {
        "revenue_ttm_usd": 4_820_000_000,
        "net_income_usd": 612_000_000,
        "diluted_eps": 3.41,
        "gross_margin_pct": 61.2,
        "cash_usd": 1_900_000_000,
        "long_term_debt_usd": 620_000_000,
        "source": "DemoCorp 10-K FY2024 (computed)",
    }
}


def get_metrics(ticker: str) -> dict:
    if CONFIG.data_mode == "live":
        from .live_metrics import fetch_live_metrics, LiveDataError
        try:
            return fetch_live_metrics(ticker)
        except LiveDataError as e:
            # Degrade gracefully: a live-data hiccup shouldn't crash the swarm.
            print(f"[warn] live metrics failed ({e}); falling back to sample data")
            return _SAMPLE_METRICS.get(ticker.upper(), _SAMPLE_METRICS["DEMO"])
    return _SAMPLE_METRICS.get(ticker.upper(), _SAMPLE_METRICS["DEMO"])


# Explicit allowlist makes the read-only contract auditable.
READ_ONLY_TOOLS = {"get_metrics": get_metrics}
