"""Live SEC EDGAR filing fetcher (read-only, keyless).

EDGAR requires a descriptive User-Agent with contact email (set SEC_USER_AGENT).
We resolve ticker -> CIK, pull recent 10-K/10-Q filings, and extract text
sections to feed the RAG index. EDGAR documents are large and inconsistent, so
extraction is deliberately conservative: grab readable text, chunk later.

Returns the same shape as the bundled sample JSON so the retriever is agnostic
to source. Raises LiveDataError on any failure so callers can fall back.
"""
from __future__ import annotations
import urllib.request
import urllib.error
import json
import re

from ..config import CONFIG

_TIMEOUT = 20
_TICKER_MAP = "https://www.sec.gov/files/company_tickers.json"
_SUBMISSIONS = "https://data.sec.gov/submissions/CIK{cik}.json"


class LiveDataError(RuntimeError):
    pass


def _headers() -> dict:
    ua = CONFIG.sec_user_agent or "equity-research-swarm contact@example.com"
    return {"User-Agent": ua, "Accept-Encoding": "identity"}

def _get(url: str) -> bytes:
    try:
        req = urllib.request.Request(url, headers=_headers())
        with urllib.request.urlopen(req, timeout=_TIMEOUT) as resp:
            return resp.read()
    except urllib.error.HTTPError as e:
        raise LiveDataError(f"EDGAR HTTP {e.code} for {url}") from e
    except urllib.error.URLError as e:
        raise LiveDataError(f"EDGAR network error: {e.reason}") from e


def _resolve_cik(ticker: str) -> str:
    data = json.loads(_get(_TICKER_MAP).decode())
    t = ticker.upper()
    for entry in data.values():
        if entry.get("ticker", "").upper() == t:
            return str(entry["cik_str"]).zfill(10)
    raise LiveDataError(f"Ticker {ticker} not found in EDGAR company list")

def _extract_relevant(text: str, limit: int = 18000) -> str:
    """Pull the analytically useful part of a filing.

    The front matter (cover page, TOC, Reg S-T legalese) is noise. The signal is
    Item 2 MD&A ('Management's Discussion and Analysis') plus what follows. We
    locate MD&A and slice from there; if not found, fall back to skipping the
    first ~8k chars of boilerplate rather than taking the very top.
    """
    low = text.lower()
    marker = "management's discussion and analysis"
    alt = "management s discussion and analysis"  # apostrophe often stripped
    idx = low.rfind(marker)
    if idx == -1:
        idx = low.rfind(alt)
    if idx == -1:
        start = 8000 if len(text) > 12000 else 0
        return text[start:start + limit]
    return text[idx:idx + limit]
def _strip_html(html: str) -> str:
    text = re.sub(r"(?is)<(script|style).*?>.*?</\1>", " ", html)
    text = re.sub(r"(?s)<[^>]+>", " ", text)
    text = re.sub(r"&#\d+;|&[a-z]+;", " ", text)
    text = re.sub(r"\s+", " ", text)
    return text.strip()


def fetch_live_filings(ticker: str, max_filings: int = 2) -> dict:
    cik = _resolve_cik(ticker)
    subs = json.loads(_get(_SUBMISSIONS.format(cik=cik)).decode())
    recent = subs.get("filings", {}).get("recent", {})
    forms = recent.get("form", [])
    accession = recent.get("accessionNumber", [])
    primary = recent.get("primaryDocument", [])
    dates = recent.get("filingDate", [])

    docs = []
    count = 0
    for i, form in enumerate(forms):
        if form not in ("10-K", "10-Q"):
            continue
        if count >= max_filings:
            break
        acc = accession[i].replace("-", "")
        doc = primary[i]
        url = f"https://www.sec.gov/Archives/edgar/data/{int(cik)}/{acc}/{doc}"
        try:
            raw = _get(url).decode("utf-8", errors="ignore")
        except LiveDataError:
            continue
        text = _strip_html(raw)
        if len(text) < 500:
            continue
        # Extract the analytically useful section (MD&A), not the cover-page front matter.
        text = _extract_relevant(text)
        docs.append({
            "id": f"{form.lower().replace('-', '')}-{dates[i]}",
            "source": f"{subs.get('name', ticker)} {form} filed {dates[i]} (SEC EDGAR)",
            "text": text,
        })
        count += 1

    if not docs:
        raise LiveDataError(f"No 10-K/10-Q filings extracted for {ticker}")
    return {"ticker": ticker.upper(), "company": subs.get("name", ticker), "documents": docs}
