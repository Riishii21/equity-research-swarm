"""PDF export for the research memo. Uses reportlab (no system deps)."""
from __future__ import annotations
import re
import tempfile
from datetime import datetime
from pathlib import Path

from reportlab.lib import colors
from reportlab.lib.pagesizes import LETTER
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, HRFlowable, Image,
)

_ACCENT = colors.HexColor("#1f3a5f")
_LIGHT = colors.HexColor("#eef2f7")
_SRC = re.compile(r"\[src:([^\]]+)\]")


def _styles():
    ss = getSampleStyleSheet()
    ss.add(ParagraphStyle("MemoTitle", parent=ss["Title"], fontSize=20,
                          textColor=_ACCENT, spaceAfter=4))
    ss.add(ParagraphStyle("MemoSub", parent=ss["Normal"], fontSize=9,
                          textColor=colors.grey, spaceAfter=12))
    ss.add(ParagraphStyle("SectionH", parent=ss["Heading2"], fontSize=13,
                          textColor=_ACCENT, spaceBefore=14, spaceAfter=6))
    ss.add(ParagraphStyle("Body", parent=ss["Normal"], fontSize=10,
                          leading=15, spaceAfter=6))
    ss.add(ParagraphStyle("Disc", parent=ss["Normal"], fontSize=8,
                          textColor=colors.grey, spaceBefore=10))
    return ss


def _render_citations(text: str) -> str:
    return _SRC.sub(r'<font size="7" color="#6b7c93"> [\1]</font>', text)


def _parse_sections(final_md: str):
    sections = []
    current_title, buf = None, []
    for line in final_md.splitlines():
        if line.startswith("## "):
            if current_title is not None:
                sections.append((current_title, "\n".join(buf).strip()))
            current_title, buf = line[3:].strip(), []
        elif line.startswith("# ") or line.strip().startswith("---") or line.strip().startswith("*This is"):
            continue
        else:
            buf.append(line)
    if current_title is not None:
        sections.append((current_title, "\n".join(buf).strip()))
    return sections


def export_pdf(state: dict, out_path: str | Path) -> str:
    out_path = str(out_path)
    ss = _styles()
    doc = SimpleDocTemplate(out_path, pagesize=LETTER,
                            topMargin=0.8 * inch, bottomMargin=0.8 * inch,
                            leftMargin=0.9 * inch, rightMargin=0.9 * inch)
    flow = []
    company = state.get("company", state.get("ticker", ""))
    ticker = state.get("ticker", "")

    flow.append(Paragraph("Equity Research Memo", ss["MemoTitle"]))
    flow.append(Paragraph(
        f"{company} ({ticker}) &nbsp;·&nbsp; generated {datetime.now():%Y-%m-%d %H:%M} "
        f"&nbsp;·&nbsp; {len(state.get('evidence', []))} sources &nbsp;·&nbsp; "
        f"critic revisions: {state.get('revisions', 0)}", ss["MemoSub"]))
    flow.append(HRFlowable(width="100%", color=_ACCENT, thickness=1.2, spaceAfter=10))

    # --- Metrics summary table ---
    m = state.get("metrics", {})
    rows = [["Metric", "Value"]]
    label_map = [
        ("revenue_ttm_usd", "Revenue"), ("net_income_usd", "Net income"),
        ("diluted_eps", "Diluted EPS"), ("gross_margin_pct", "Gross margin %"),
        ("price_usd", "Price"), ("market_cap_usd", "Market cap"),
    ]
    for key, label in label_map:
        v = m.get(key)
        if v is None:
            continue
        if key.endswith("_usd") and key != "diluted_eps":
            v = f"${v:,}"
        elif key.endswith("_pct"):
            v = f"{v}%"
        rows.append([label, str(v)])
    if len(rows) > 1:
        t = Table(rows, colWidths=[2.2 * inch, 3.8 * inch])
        t.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, 0), _ACCENT),
            ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
            ("FONTSIZE", (0, 0), (-1, -1), 9),
            ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, _LIGHT]),
            ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#cdd6e0")),
            ("PADDING", (0, 0), (-1, -1), 5),
        ]))
        flow.append(t)
        flow.append(Spacer(1, 8))

    # --- Charts (live enrichment; optional) ---
    tmp = tempfile.mkdtemp(prefix="ers_charts_")
    try:
        from .charts import revenue_chart, margin_chart
        rc = revenue_chart(state.get("financial_history", []), tmp)
        if rc:
            flow.append(Image(rc, width=6.0 * inch, height=2.8 * inch))
            flow.append(Spacer(1, 6))
        mc = margin_chart(state.get("ratio_history", []), tmp)
        if mc:
            flow.append(Image(mc, width=6.0 * inch, height=2.8 * inch))
            flow.append(Spacer(1, 6))
    except Exception:
        pass

    # --- Report sections (the analysis body) ---
    for title, body in _parse_sections(state.get("final", "")):
        flow.append(Paragraph(title, ss["SectionH"]))
        for para in [p for p in body.split("\n") if p.strip()]:
            txt = para.strip().lstrip("- ").strip()
            flow.append(Paragraph(_render_citations(txt), ss["Body"]))

    # --- Peer comparison table (live enrichment) ---
    peers = state.get("peers", [])
    if peers:
        flow.append(Paragraph("Peer Comparison", ss["SectionH"]))
        prows = [["Company", "Ticker", "Price", "Market Cap"]]
        for p in peers:
            mc2 = p.get("market_cap")
            mc_s = f"${mc2/1e9:,.1f}B" if mc2 else "-"
            pr = p.get("price")
            pr_s = f"${pr:,.2f}" if pr else "-"
            prows.append([p.get("name", "")[:34], p.get("symbol", ""), pr_s, mc_s])
        pt = Table(prows, colWidths=[2.9 * inch, 0.9 * inch, 1.0 * inch, 1.2 * inch])
        pt.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, 0), _ACCENT),
            ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
            ("FONTSIZE", (0, 0), (-1, -1), 8),
            ("ALIGN", (2, 0), (-1, -1), "RIGHT"),
            ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, _LIGHT]),
            ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#cdd6e0")),
            ("PADDING", (0, 0), (-1, -1), 4),
        ]))
        flow.append(pt)
        flow.append(Spacer(1, 8))

    # --- 5-year financial summary table (live enrichment) ---
    hist = state.get("financial_history", [])
    if hist:
        flow.append(Paragraph("Financial Summary (5-Year)", ss["SectionH"]))
        hrows = [["Fiscal Year", "Revenue", "Net Income", "Diluted EPS"]]
        for h in hist:
            rev = h.get("revenue")
            ni = h.get("net_income")
            eps = h.get("eps_diluted")
            hrows.append([
                str(h.get("fiscal_year", "")),
                f"${rev/1e9:,.1f}B" if rev else "-",
                f"${ni/1e9:,.1f}B" if ni else "-",
                f"{eps}" if eps is not None else "-",
            ])
        ht = Table(hrows, colWidths=[1.4 * inch, 1.6 * inch, 1.6 * inch, 1.4 * inch])
        ht.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, 0), _ACCENT),
            ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
            ("FONTSIZE", (0, 0), (-1, -1), 8),
            ("ALIGN", (1, 0), (-1, -1), "RIGHT"),
            ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, _LIGHT]),
            ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#cdd6e0")),
            ("PADDING", (0, 0), (-1, -1), 4),
        ]))
        flow.append(ht)
        flow.append(Spacer(1, 8))

    # --- Financial statements (income / balance / cash flow) ---
    stmts = state.get("statements", {})

    def _stmt_table(title, srows):
        if not srows:
            return
        flow.append(Paragraph(title, ss["SectionH"]))
        data = [["Line item", "Value"]]
        for x in srows:
            v = x["value"]
            if isinstance(v, (int, float)) and abs(v) >= 1e9:
                vs = f"${v/1e9:,.2f}B"
            elif isinstance(v, (int, float)) and abs(v) >= 1e6:
                vs = f"${v/1e6:,.1f}M"
            elif isinstance(v, (int, float)):
                vs = f"{v:,}"
            else:
                vs = str(v)
            data.append([x["label"], vs])
        tt = Table(data, colWidths=[3.6 * inch, 2.4 * inch])
        tt.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, 0), _ACCENT),
            ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
            ("FONTSIZE", (0, 0), (-1, -1), 8),
            ("ALIGN", (1, 0), (-1, -1), "RIGHT"),
            ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, _LIGHT]),
            ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#cdd6e0")),
            ("PADDING", (0, 0), (-1, -1), 4),
        ]))
        flow.append(tt)
        flow.append(Spacer(1, 8))

    if stmts.get("income") or stmts.get("balance") or stmts.get("cashflow"):
        period = stmts.get("period", "")
        _stmt_table(f"Income Statement{' · FY'+str(period) if period else ''}", stmts.get("income"))
        _stmt_table("Balance Sheet", stmts.get("balance"))
        _stmt_table("Cash Flow Statement", stmts.get("cashflow"))

    # Sources table
    flow.append(Paragraph("Sources", ss["SectionH"]))
    srows = [["ID", "Source"]]
    for e in state.get("evidence", []):
        srows.append([e["id"], e.get("source", "")])
    st = Table(srows, colWidths=[2.0 * inch, 4.0 * inch])
    st.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), _ACCENT),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("FONTSIZE", (0, 0), (-1, -1), 8),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, _LIGHT]),
        ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#cdd6e0")),
        ("PADDING", (0, 0), (-1, -1), 4),
    ]))
    flow.append(st)

    flow.append(HRFlowable(width="100%", color=colors.lightgrey, thickness=0.5, spaceBefore=12))
    flow.append(Paragraph(
        "This is an engineering demonstration, not investment advice. "
        "No buy/sell/hold recommendation is expressed or implied.", ss["Disc"]))

    doc.build(flow)
    return out_path