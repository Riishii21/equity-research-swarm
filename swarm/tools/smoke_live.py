"""Live-data smoke test. Run on a machine with network + keys:

    DATA_MODE=live FMP_API_KEY=xxx SEC_USER_AGENT="you you@email.com" \\
        python -m swarm.tools.smoke_live AAPL

Tests EDGAR and the metrics provider in isolation, so you can confirm the data
layer works before running the full swarm. Prints clear pass/fail per source.
"""
import sys
from ..config import CONFIG


def main():
    ticker = sys.argv[1] if len(sys.argv) > 1 else "AAPL"
    print(f"Smoke testing live data for {ticker}")
    print(f"  metrics_provider={CONFIG.metrics_provider}  data_mode={CONFIG.data_mode}\n")

    print("[1/2] SEC EDGAR filings ...")
    try:
        from ..rag.live_filings import fetch_live_filings
        data = fetch_live_filings(ticker)
        print(f"  OK — {data['company']}: {len(data['documents'])} filing(s)")
        for d in data["documents"]:
            print(f"     - {d['source']} ({len(d['text'])} chars)")
    except Exception as e:
        print(f"  FAIL — {e}")

    print("\n[2/2] Live metrics ...")
    try:
        from .live_metrics import fetch_live_metrics
        m = fetch_live_metrics(ticker)
        print(f"  OK — source: {m['source']}")
        for k, v in m.items():
            if k != "source":
                print(f"     - {k}: {v}")
    except Exception as e:
        print(f"  FAIL — {e}")

    print("\nIf both pass, run the full swarm with DATA_MODE=live.")


if __name__ == "__main__":
    main()
