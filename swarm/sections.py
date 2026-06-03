"""Report section definitions.

Each section drives its own retrieval query (so evidence is section-specific
and deep) and carries a writing instruction.
"""
from __future__ import annotations
from dataclasses import dataclass


@dataclass
class Section:
    key: str
    title: str
    query: str
    instruction: str


SECTIONS: list[Section] = [
    Section(
        "exec_summary", "Executive Summary",
        "overall financial performance growth outlook key risks",
        "Write a 3-4 sentence executive summary synthesizing the most important "
        "findings: headline financials, the core growth story, and the single "
        "biggest risk.",
    ),
    Section(
        "business", "Business Overview",
        "business operations products segments revenue sources how company makes money",
        "Describe what the company does, its main products/segments, and how it "
        "generates revenue. 2-3 short paragraphs.",
    ),
    Section(
        "financials", "Financial Performance",
        "revenue net income margin growth quarter year over year results of operations",
        "Analyze recent financial performance using the metrics and filing "
        "evidence: revenue, profitability, margins, and notable changes. Reference "
        "specific numbers. 2-3 paragraphs.",
    ),
    Section(
        "valuation", "Valuation",
        "valuation price earnings market capitalization price target multiples",
        "Discuss valuation using available data (price, market cap, EPS, any "
        "analyst targets). Present figures and context only - do NOT give a "
        "buy/sell/hold recommendation. 1-2 paragraphs.",
    ),
    Section(
        "competitive", "Competitive Position",
        "competition competitors market share competitive advantages industry rivals",
        "Assess the company's competitive position and main competitive pressures "
        "as described in the filings. 1-2 paragraphs.",
    ),
    Section(
        "risks", "Risk Factors",
        "risk factors uncertainties adverse material risks challenges threats",
        "Summarize the key stated risk factors. Prefer the most material risks. "
        "Use short grouped points, each grounded in evidence.",
    ),
    Section(
        "outlook", "Outlook",
        "guidance outlook future expectations forward-looking management expects",
        "Summarize management's stated guidance and outlook, plus any forward-"
        "looking commentary. 1-2 paragraphs. Clearly mark expectations as the "
        "company's own, not predictions.",
    ),
]