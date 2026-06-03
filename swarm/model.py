"""Provider-agnostic LLM interface.

One method: complete(system, user) -> str.
Backends: mock (offline, deterministic), groq, anthropic, openai.
The mock is intentionally structured rather than random so the full graph
produces a coherent, grounded brief with no API key — this is what makes
the demo and the eval harness reproducible.
"""
from __future__ import annotations
import json
from typing import Protocol
from .config import CONFIG


class LLM(Protocol):
    def complete(self, system: str, user: str) -> str: ...


class MockLLM:
    """Deterministic, offline. Routes on a tag in the system prompt so each
    agent gets a sensible canned behaviour grounded in the provided context."""

    def complete(self, system: str, user: str) -> str:
        role = _role_tag(system)
        if role == "planner":
            return json.dumps({
                "subquestions": [
                    "What is the company's recent revenue and profitability?",
                    "What guidance or outlook has management given?",
                    "What are the key stated risk factors?",
                ]
            })
        if role == "analyst":
            # Write a section body strictly from the evidence handed in.
            claims = _evidence_lines(user)
            if not claims:
                return "Insufficient evidence retrieved for this section."
            return "\n".join(f"- {c}" for c in claims)
        if role == "critic":
            # Approve only if every draft bullet maps to an evidence id.
            unsupported = _find_unsupported(user)
            if unsupported:
                return json.dumps({"approved": False, "unsupported": unsupported})
            return json.dumps({"approved": True, "unsupported": []})
        if role == "synthesizer":
            return user.strip() + "\n\n---\n*This is an engineering demo, not investment advice.*"
        return "OK"


def _role_tag(system: str) -> str:
    for tag in ("planner", "analyst", "critic", "synthesizer"):
        if f"[role:{tag}]" in system:
            return tag
    return "unknown"


def _evidence_lines(user: str) -> list[str]:
    """Pull 'EVIDENCE' lines the orchestrator embeds, keep their [src:..] tags."""
    import re as _re
    out = []
    for line in user.splitlines():
        line = line.strip()
        if line.startswith("EVIDENCE"):
            rest = line[len("EVIDENCE"):].strip()
            # format: "[src:id]: text [src:id]" -> drop the ": " right after the first tag
            rest = _re.sub(r"^(\[src:[^\]]+\]):\s*", r"\1 ", rest)
            out.append(rest)
    return out


def _find_unsupported(user: str) -> list[str]:
    """A draft bullet is unsupported if it carries no [src:...] citation tag."""
    bad = []
    for line in user.splitlines():
        s = line.strip()
        if s.startswith("- ") and "[src:" not in s:
            bad.append(s[2:])
    return bad


def _real_llm():
    p = CONFIG.model_provider
    if p == "groq":
        from langchain_groq import ChatGroq
        client = ChatGroq(model=CONFIG.model_name, api_key=CONFIG.groq_api_key, temperature=0.2)
    elif p == "anthropic":
        from langchain_anthropic import ChatAnthropic
        client = ChatAnthropic(model=CONFIG.model_name, api_key=CONFIG.anthropic_api_key, temperature=0.2)
    elif p == "openai":
        from langchain_openai import ChatOpenAI
        client = ChatOpenAI(model=CONFIG.model_name, api_key=CONFIG.openai_api_key, temperature=0.2)
    else:
        raise ValueError(f"Unknown provider: {p}")

    class _Wrapper:
        def complete(self, system: str, user: str) -> str:
            from langchain_core.messages import SystemMessage, HumanMessage
            resp = client.invoke([SystemMessage(content=system), HumanMessage(content=user)])
            return resp.content if isinstance(resp.content, str) else str(resp.content)

    return _Wrapper()


def get_llm() -> LLM:
    return MockLLM() if CONFIG.model_provider == "mock" else _real_llm()
