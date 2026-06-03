"""CLI: python -m swarm.run --ticker DEMO [--trace] [--pdf out.pdf]"""
import argparse
from .graph import run_swarm


def main():
    ap = argparse.ArgumentParser(description="Equity Research Swarm")
    ap.add_argument("--ticker", default="DEMO")
    ap.add_argument("--trace", action="store_true", help="print the execution trace")
    ap.add_argument("--pdf", metavar="PATH", help="also export the memo to a PDF")
    args = ap.parse_args()

    state = run_swarm(args.ticker)

    print("\n" + "=" * 60)
    print(state["final"])
    print("=" * 60)
    print(f"\nSections: {len(state.get('sections', {}))}  |  "
          f"Critic revisions: {state.get('revisions', 0)}  |  "
          f"Evidence passages: {len(state.get('evidence', []))}")
    if args.trace:
        print("\n" + state["tracer"].render())
    if args.pdf:
        from .export.pdf_export import export_pdf
        path = export_pdf(state, args.pdf)
        print(f"\nPDF written to {path}")


if __name__ == "__main__":
    main()