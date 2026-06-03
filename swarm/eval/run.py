"""Eval harness.

Two metrics that turn 'it feels reliable' into numbers:

1. Groundedness — share of claims in the final brief that carry a valid
   citation to retrieved evidence or a tool result.
2. Critic catch-rate — inject deliberately unsupported claims and measure how
   often the critic flags them. This is the direct test that the
   hallucination-defense loop actually works.

Runs fully offline in mock mode, so results are reproducible.
"""
from __future__ import annotations
import re

from ..graph import run_swarm, _critic, SwarmState
from ..observability.tracer import Tracer

_SRC = re.compile(r"\[src:([^\]]+)\]")


def groundedness(final: str, valid_ids: set[str]) -> float:
    bullets = [b for b in final.splitlines() if b.strip().startswith("- ")]
    if not bullets:
        return 0.0
    grounded = 0
    for b in bullets:
        ids = _SRC.findall(b)
        if ids and all(i in valid_ids for i in ids):
            grounded += 1
    return grounded / len(bullets)


def critic_catch_rate() -> float:
    """Feed the critic drafts with planted unsupported claims; expect rejection."""
    cases = [
        {"draft": "- The stock will double next year\n- [src:metrics] EPS is 3.41",
         "should_reject": True},
        {"draft": "- Revenue is hot and rising fast\n- Profits look amazing",
         "should_reject": True},
        {"draft": "- [src:metrics] EPS is 3.41 [src:metrics]",
         "should_reject": False},
    ]
    correct = 0
    for c in cases:
        state: SwarmState = {
            "ticker": "DEMO", "draft": c["draft"],
            "evidence": [{"id": "10k-2024-income#0", "source": "x", "text": "y"}],
            "revisions": 0, "tracer": Tracer(),
        }
        out = _critic(state)
        rejected = not out["approved"]
        if rejected == c["should_reject"]:
            correct += 1
    return correct / len(cases)


def run():
    state = run_swarm("DEMO")
    valid = {e["id"] for e in state["evidence"]} | {"metrics"}
    g = groundedness(state["final"], valid)
    c = critic_catch_rate()

    print("=" * 50)
    print("EVAL REPORT (mock mode, reproducible)")
    print("=" * 50)
    print(f"Groundedness (claims with valid citations): {g:6.1%}")
    print(f"Critic hallucination-catch rate:            {c:6.1%}")
    print(f"Critic revisions triggered on real run:     {state.get('revisions', 0)}")
    print("=" * 50)
    return {"groundedness": g, "catch_rate": c}


if __name__ == "__main__":
    run()
