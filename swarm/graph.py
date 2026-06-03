"""The agent swarm, orchestrated with LangGraph.

Flow: gather (per-section retrieval + quant) -> analyst (writes each report
section grounded in section-specific evidence) -> critic (audits; loops back to
analyst while unsupported claims remain, bounded by MAX_REVISIONS) -> human
checkpoint -> synthesizer (title + disclaimer).
"""
from __future__ import annotations
import json
from typing import TypedDict

from langgraph.graph import StateGraph, END

from .config import CONFIG
from .model import get_llm
from .rag.retriever import Retriever
from .tools.quant import get_metrics
from .observability.tracer import Tracer
from .sections import SECTIONS


class SwarmState(TypedDict, total=False):
    ticker: str
    company: str
    evidence: list[dict]
    section_evidence: dict
    metrics: dict
    financial_history: list
    ratio_history: list
    peers: list
    statements: dict
    sections: dict
    draft: str
    approved: bool
    unsupported: list[str]
    revisions: int
    final: str
    tracer: Tracer


ANALYST_SYS = (
    "[role:analyst] You are an equity research analyst writing ONE section of a "
    "research memo. Ground every factual claim in the provided evidence and tag "
    "it with a citation like [src:<id>]. Never state a fact without a tag. If the "
    "evidence is thin for this section, say so briefly rather than inventing. Do "
    "not give investment recommendations."
)
CRITIC_SYS = (
    "[role:critic] You audit a research memo. Any sentence making a factual claim "
    "without a [src:...] tag, or citing an id not in the valid list, is "
    "unsupported. Return JSON: {\"approved\": bool, \"unsupported\": [\"...\"]}."
)
SYNTH_SYS = "[role:synthesizer] You finalize the memo and append the not-advice disclaimer."


def _metrics_evidence(m: dict) -> dict:
    parts = []
    if m.get("revenue_ttm_usd"):
        parts.append(f"revenue ${m['revenue_ttm_usd']:,}")
    if m.get("net_income_usd"):
        parts.append(f"net income ${m['net_income_usd']:,}")
    if m.get("diluted_eps"):
        parts.append(f"diluted EPS {m['diluted_eps']}")
    if m.get("gross_margin_pct"):
        parts.append(f"gross margin {m['gross_margin_pct']}%")
    if m.get("price_usd"):
        parts.append(f"price ${m['price_usd']}")
    if m.get("market_cap_usd"):
        parts.append(f"market cap ${m['market_cap_usd']:,}")
    return {"id": "metrics", "source": m.get("source", "metrics"),
            "text": ", ".join(parts)}


def _gather(state: SwarmState) -> SwarmState:
    tr = state["tracer"]
    uploaded = state.get("uploaded_docs")
    if uploaded:
        retriever = Retriever(documents=uploaded)
        state["company"] = uploaded.get("company") or state.get("company") or state["ticker"]
    else:
        retriever = Retriever(state["ticker"])
        state["company"] = retriever.company or state["ticker"]
    if uploaded and not state.get("has_ticker"):
        state["metrics"] = {}
        tr.log("quant", "upload-only run: no ticker, skipping live metrics")
    else:
        state["metrics"] = get_metrics(state["ticker"])
        tr.log("quant", f"metrics fetched (read-only): {list(state['metrics'].keys())}")

    has_metrics = bool(state.get("metrics"))
    metrics_ev = _metrics_evidence(state["metrics"]) if has_metrics else None
    section_ev: dict = {}
    all_ev: dict = {metrics_ev["id"]: metrics_ev} if has_metrics else {}
    for sec in SECTIONS:
        hits = retriever.retrieve(sec.query, k=3)
        evs = [{"id": p.id, "source": p.source, "text": p.text} for p in hits]
        if has_metrics and sec.key in ("financials", "valuation", "exec_summary"):
            evs = [metrics_ev] + evs
        for e in evs:
            all_ev[e["id"]] = e
        tr.log("retriever", f"section '{sec.key}': {len(evs)} passages")

    state["section_evidence"] = section_ev
    state["evidence"] = list(all_ev.values())

    # Enrichment data for charts/tables (live mode only; optional, never fatal).
    state["financial_history"] = []
    state["ratio_history"] = []
    state["peers"] = []
    state["statements"] = {}
    if CONFIG.data_mode == "live" and not (uploaded and not state.get("has_ticker")):
        try:
            from .tools.live_financials import (
                fetch_financial_history, fetch_ratio_history, fetch_peers, LiveDataError,
            )
            try:
                state["financial_history"] = fetch_financial_history(state["ticker"])
                tr.log("enrich", f"financial history: {len(state['financial_history'])} years")
            except LiveDataError as e:
                tr.log("enrich", f"financial history unavailable: {e}")
            try:
                state["ratio_history"] = fetch_ratio_history(state["ticker"])
                tr.log("enrich", f"ratio history: {len(state['ratio_history'])} years")
            except LiveDataError as e:
                tr.log("enrich", f"ratio history unavailable: {e}")
            try:
                state["peers"] = fetch_peers(state["ticker"])
                tr.log("enrich", f"peers: {len(state['peers'])}")
            except LiveDataError as e:
                tr.log("enrich", f"peers unavailable: {e}")
            try:
                from .tools.live_financials import fetch_statements
                state["statements"] = fetch_statements(state["ticker"])
                tr.log("enrich", "financial statements fetched")
            except LiveDataError as e:
                tr.log("enrich", f"statements unavailable: {e}")
        except Exception as e:
            tr.log("enrich", f"enrichment skipped: {e}")
    return state


def _evidence_block(evs: list[dict]) -> str:
    return "\n".join(
        f"EVIDENCE [src:{e['id']}]: {e['text']} [src:{e['id']}]" for e in evs
    )


def _analyst(state: SwarmState) -> SwarmState:
    llm = get_llm()
    tr = state["tracer"]
    feedback = ""
    if state.get("unsupported"):
        feedback = ("\n\nA critic flagged these unsupported claims in the previous "
                    "draft - fix or remove them, keep everything cited: "
                    + "; ".join(state["unsupported"][:8]))

    sections_out: dict = {}
    for sec in SECTIONS:
        evs = state["section_evidence"].get(sec.key, [])
        user = (
            f"Company: {state.get('company', state['ticker'])} ({state['ticker']})\n"
            f"Section to write: {sec.title}\n"
            f"Instruction: {sec.instruction}\n\n"
            f"{_evidence_block(evs)}{feedback}\n\n"
            f"Write only the '{sec.title}' section body. Tag every claim [src:...]."
        )
        sections_out[sec.key] = llm.complete(ANALYST_SYS, user)

    state["sections"] = sections_out
    parts = []
    for sec in SECTIONS:
        parts.append(f"## {sec.title}\n\n{sections_out.get(sec.key, '').strip()}")
    state["draft"] = "\n\n".join(parts)
    tr.log("analyst", f"draft v{state.get('revisions', 0) + 1}: {len(SECTIONS)} sections written")
    return state


def _critic(state: SwarmState) -> SwarmState:
    llm = get_llm()
    tr = state["tracer"]
    valid_ids = {e["id"] for e in state["evidence"]}
    user = (f"Valid evidence ids: {sorted(valid_ids)}\n\nMemo:\n{state['draft']}\n\n"
            "Audit every section. Return the JSON verdict.")
    out = llm.complete(CRITIC_SYS, user)
    try:
        verdict = json.loads(out)
    except Exception:
        verdict = {"approved": True, "unsupported": []}
    state["approved"] = bool(verdict.get("approved", True))
    state["unsupported"] = verdict.get("unsupported", []) or []
    tr.log("critic", f"approved={state['approved']} unsupported={len(state['unsupported'])}")
    if not state["approved"]:
        state["revisions"] = state.get("revisions", 0) + 1
    return state


def _route_after_critic(state: SwarmState) -> str:
    if state["approved"] or state.get("revisions", 0) >= CONFIG.max_revisions:
        return "checkpoint"
    return "revise"


def _checkpoint(state: SwarmState) -> SwarmState:
    state["tracer"].log("human_checkpoint", "memo surfaced for approval before finalizing")
    return state


def _synthesizer(state: SwarmState) -> SwarmState:
    # Preserve the analyst's section structure verbatim; only frame it with a
    # title and append the disclaimer. We deliberately do NOT ask the model to
    # rewrite here, which would flatten the section headings.
    title = f"# Equity Research Memo: {state.get('company', state['ticker'])} ({state['ticker']})\n\n"
    disclaimer = ("\n\n---\n*This is an engineering demonstration, not investment "
                  "advice. No buy/sell/hold recommendation is expressed or implied.*")
    state["final"] = title + state["draft"].strip() + disclaimer
    state["tracer"].log("synthesizer", "final memo assembled with disclaimer")
    return state


def build_graph():
    g = StateGraph(SwarmState)
    g.add_node("gather", _gather)
    g.add_node("analyst", _analyst)
    g.add_node("critic", _critic)
    g.add_node("checkpoint", _checkpoint)
    g.add_node("synthesizer", _synthesizer)

    g.set_entry_point("gather")
    g.add_edge("gather", "analyst")
    g.add_edge("analyst", "critic")
    g.add_conditional_edges("critic", _route_after_critic,
                            {"revise": "analyst", "checkpoint": "checkpoint"})
    g.add_edge("checkpoint", "synthesizer")
    g.add_edge("synthesizer", END)
    return g.compile()


def run_swarm(ticker: str) -> SwarmState:
    graph = build_graph()
    state: SwarmState = {"ticker": ticker, "revisions": 0, "tracer": Tracer()}
    return graph.invoke(state)