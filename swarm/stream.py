"""Streaming swarm runner — yields progress events for the frontend animation."""
from __future__ import annotations
from typing import Iterator

from .config import CONFIG
from .observability.tracer import Tracer
from .graph import (
    SwarmState, _gather, _analyst, _critic, _checkpoint, _synthesizer,
)
from .sections import SECTIONS


def run_swarm_streaming(ticker: str, uploaded_docs: dict | None = None) -> Iterator[dict]:
    """Yield progress events, then a final 'done' event with the full result.
    If uploaded_docs is provided, runs the document path; ticker optional."""
    has_ticker = bool(ticker and ticker.strip())
    state: SwarmState = {"ticker": ticker or "", "revisions": 0, "tracer": Tracer(),
                         "uploaded_docs": uploaded_docs, "has_ticker": has_ticker}

    label = (uploaded_docs.get("company") if uploaded_docs else ticker.upper())
    yield {"stage": "start", "label": f"Researching {label}", "status": "active"}

    yield {"stage": "planner", "label": "Planning research sections", "status": "active"}
    state = _gather(state)
    yield {"stage": "planner", "label": f"{len(SECTIONS)} sections planned", "status": "done"}
    yield {
        "stage": "retriever",
        "label": f"Retrieved {len(state.get('evidence', []))} grounded passages",
        "status": "done",
        "detail": [e["source"] for e in state.get("evidence", [])[:6]],
    }
    yield {
        "stage": "quant",
        "label": "Financial metrics fetched (read-only)",
        "status": "done",
        "detail": list(state.get("metrics", {}).keys()),
    }

    while True:
        yield {"stage": "analyst", "label": "Analyst drafting sourced memo", "status": "active"}
        state = _analyst(state)
        yield {"stage": "analyst", "label": f"Draft v{state.get('revisions', 0) + 1} written", "status": "done"}

        yield {"stage": "critic", "label": "Critic auditing every claim", "status": "active"}
        state = _critic(state)
        if state["approved"] or state.get("revisions", 0) >= CONFIG.max_revisions:
            yield {
                "stage": "critic",
                "label": ("All claims verified" if state["approved"]
                          else f"Stopped after {state['revisions']} revisions"),
                "status": "done",
            }
            break
        else:
            yield {
                "stage": "critic",
                "label": f"Found {len(state['unsupported'])} unsupported claims - revising",
                "status": "revise",
            }

    yield {"stage": "checkpoint", "label": "Human-checkpoint gate", "status": "done"}
    state = _checkpoint(state)
    yield {"stage": "synthesizer", "label": "Finalizing memo", "status": "active"}
    state = _synthesizer(state)
    yield {"stage": "synthesizer", "label": "Memo complete", "status": "done"}

    yield {
        "stage": "done",
        "status": "done",
        "result": {
            "company": state.get("company", ticker),
            "ticker": state.get("ticker", ticker),
            "final": state.get("final", ""),
            "metrics": state.get("metrics", {}),
            "evidence": state.get("evidence", []),
            "financial_history": state.get("financial_history", []),
            "ratio_history": state.get("ratio_history", []),
            "peers": state.get("peers", []),
            "statements": state.get("statements", {}),
            "revisions": state.get("revisions", 0),
        },
    }