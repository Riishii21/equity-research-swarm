"""Tests. Run: python -m pytest tests/ -v  (or just python tests/test_swarm.py)"""
from swarm.graph import run_swarm, build_graph, SwarmState, _critic, _analyst
from swarm.observability.tracer import Tracer
from swarm.rag.retriever import Retriever


def test_swarm_runs_end_to_end():
    state = run_swarm("DEMO")
    assert state["final"]
    assert "not investment advice" in state["final"].lower()
    assert len(state["evidence"]) > 0


def test_every_claim_is_cited():
    state = run_swarm("DEMO")
    bullets = [b for b in state["final"].splitlines() if b.strip().startswith("- ")]
    assert bullets, "expected at least one claim"
    for b in bullets:
        assert "[src:" in b, f"uncited claim: {b}"


def test_critic_rejects_unsupported_claim():
    """The hallucination-defense loop: an uncited claim must be rejected."""
    state: SwarmState = {
        "ticker": "DEMO",
        "draft": "- The stock is a strong buy\n- [src:metrics] EPS is 3.41 [src:metrics]",
        "evidence": [{"id": "10k-2024-income#0", "source": "x", "text": "y"}],
        "revisions": 0, "tracer": Tracer(),
    }
    out = _critic(state)
    assert out["approved"] is False
    assert any("strong buy" in u for u in out["unsupported"])


def test_critic_loop_forces_revision():
    """Force the analyst to emit an uncited bullet once, prove the graph loops
    back through analyst and the revision counter increments."""
    state: SwarmState = {
        "ticker": "DEMO",
        "draft": "- unsupported claim with no tag",
        "evidence": [{"id": "10k-2024-income#0", "source": "x", "text": "y"}],
        "revisions": 0, "tracer": Tracer(),
    }
    out = _critic(state)
    assert out["approved"] is False
    assert out["revisions"] == 1


def test_retriever_returns_cited_passages():
    r = Retriever("DEMO")
    hits = r.retrieve("revenue and profitability", k=2)
    assert len(hits) == 2
    assert all(h.source for h in hits)
    assert all(h.id for h in hits)


def test_tools_are_read_only():
    """Guardrail contract: no mutating tool exists in the allowlist."""
    from swarm.tools.quant import READ_ONLY_TOOLS
    mutating = {"buy", "sell", "trade", "transfer", "delete", "write", "send"}
    for name in READ_ONLY_TOOLS:
        assert not any(m in name.lower() for m in mutating)


if __name__ == "__main__":
    fns = [v for k, v in dict(globals()).items() if k.startswith("test_")]
    passed = 0
    for fn in fns:
        try:
            fn(); print(f"PASS  {fn.__name__}"); passed += 1
        except AssertionError as e:
            print(f"FAIL  {fn.__name__}: {e}")
    print(f"\n{passed}/{len(fns)} passed")
