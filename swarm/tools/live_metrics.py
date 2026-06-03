"""Live financial-metric fetchers (read-only).

Providers: FMP (Financial Modeling Prep) and Alpha Vantage, both free-tier.
Defensive by design — any network/parse failure raises a clear LiveDataError
that the caller can catch and fall back to sample mode, rather than crashing
the whole swarm. Still read-only: these only GET, never mutate.

Cannot be exercised in a no-network sandbox; test on a machine with outbound
access and a free API key. See README 'Live mode'.
"""
from __future__ import annotations
import urllib.request
import urllib.error
import json

from ..config import CONFIG

_TIMEOUT = 15


class LiveDataError(RuntimeError):
    pass


def _get_json(url: str) -> dict | list:
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "equity-research-swarm/1.0"})
        with urllib.request.urlopen(req, timeout=_TIMEOUT) as resp:
            return json.loads(resp.read().decode())
    except urllib.error.HTTPError as e:
        raise LiveDataError(f"HTTP {e.code} from data provider for {url.split('?')[0]}") from e
    except urllib.error.URLError as e:
        raise LiveDataError(f"Network error reaching data provider: {e.reason}") from e
    except (json.JSONDecodeError, ValueError) as e:
        raise LiveDataError("Provider returned non-JSON / unexpected payload") from e


def _from_fmp(ticker: str) -> dict:
    key = CONFIG.fmp_api_key
    if not key:
        raise LiveDataError("FMP_API_KEY not set")
    # FMP retired /api/v3/ on 2025-08-31. Stable API: /stable/<endpoint>?symbol=...
    base = "https://financialmodelingprep.com/stable"
    profile = _get_json(f"{base}/profile?symbol={ticker}&apikey={key}")
    income = _get_json(f"{base}/income-statement?symbol={ticker}&limit=1&apikey={key}")
    if isinstance(profile, dict) and profile.get("Error Message"):
        raise LiveDataError(f"FMP: {profile['Error Message']}")
    if not profile or not income:
        raise LiveDataError(f"FMP returned no data for {ticker} (check ticker / plan limits)")
    # FMP may return either a list or a single object depending on endpoint/plan.
    p = profile[0] if isinstance(profile, list) else profile
    i = income[0] if isinstance(income, list) else income
    revenue = i.get("revenue")
    gross = i.get("grossProfit")
    return {
        "revenue_ttm_usd": revenue,
        "net_income_usd": i.get("netIncome"),
        "diluted_eps": i.get("epsDiluted") or i.get("epsdiluted") or i.get("eps"),
        "gross_margin_pct": round(100 * gross / revenue, 1) if (gross and revenue) else None,
        "price_usd": p.get("price"),
        "market_cap_usd": p.get("marketCap") or p.get("mktCap"),
        "source": f"FMP profile + income statement ({i.get('date', 'latest')})",
    }

def _from_alphavantage(ticker: str) -> dict:
    key = CONFIG.alphavantage_api_key
    if not key:
        raise LiveDataError("ALPHAVANTAGE_API_KEY not set")
    base = "https://www.alphavantage.co/query"
    overview = _get_json(f"{base}?function=OVERVIEW&symbol={ticker}&apikey={key}")
    if not overview or "Symbol" not in overview:
        # AV returns {} or a rate-limit note rather than an error code
        note = overview.get("Note") or overview.get("Information") if isinstance(overview, dict) else None
        raise LiveDataError(note or f"Alpha Vantage returned no overview for {ticker}")

    def _num(v):
        try:
            return float(v)
        except (TypeError, ValueError):
            return None

    return {
        "revenue_ttm_usd": _num(overview.get("RevenueTTM")),
        "net_income_usd": None,  # not in OVERVIEW; would need INCOME_STATEMENT call
        "diluted_eps": _num(overview.get("DilutedEPSTTM")),
        "gross_margin_pct": (round(_num(overview.get("GrossProfitTTM")) /
                             _num(overview.get("RevenueTTM")) * 100, 1)
                             if _num(overview.get("RevenueTTM")) else None),
        "price_usd": None,
        "market_cap_usd": _num(overview.get("MarketCapitalization")),
        "source": "Alpha Vantage OVERVIEW (TTM)",
    }


def fetch_live_metrics(ticker: str) -> dict:
    provider = CONFIG.metrics_provider.lower()
    if provider == "alphavantage":
        return _from_alphavantage(ticker)
    return _from_fmp(ticker)
