"""Chart generation for the research memo. Renders matplotlib charts to PNG."""
from __future__ import annotations
from pathlib import Path

_ACCENT = "#1f3a5f"
_ACCENT2 = "#c0883f"
_GRID = "#d8dee6"


def _setup():
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    plt.rcParams.update({
        "font.size": 9, "axes.edgecolor": _GRID, "axes.grid": True,
        "grid.color": _GRID, "grid.linewidth": 0.6, "axes.axisbelow": True,
        "figure.dpi": 150,
    })
    return plt


def revenue_chart(history: list[dict], out_dir: str) -> str | None:
    rows = [h for h in reversed(history) if h.get("revenue")]
    if len(rows) < 2:
        return None
    plt = _setup()
    years = [str(h["fiscal_year"]) for h in rows]
    rev = [h["revenue"] / 1e9 for h in rows]
    ni = [(h.get("net_income") or 0) / 1e9 for h in rows]

    fig, ax = plt.subplots(figsize=(6.4, 3.0))
    x = range(len(years))
    w = 0.38
    ax.bar([i - w / 2 for i in x], rev, w, label="Revenue", color=_ACCENT)
    ax.bar([i + w / 2 for i in x], ni, w, label="Net income", color=_ACCENT2)
    ax.set_xticks(list(x))
    ax.set_xticklabels(years)
    ax.set_ylabel("USD billions")
    ax.set_title("Revenue and Net Income by Fiscal Year", color=_ACCENT, fontweight="bold")
    ax.legend(frameon=False, fontsize=8)
    fig.tight_layout()
    path = str(Path(out_dir) / "chart_revenue.png")
    fig.savefig(path, bbox_inches="tight")
    plt.close(fig)
    return path


def margin_chart(ratios: list[dict], out_dir: str) -> str | None:
    rows = [r for r in reversed(ratios) if r.get("gross_margin") is not None]
    if len(rows) < 2:
        return None
    plt = _setup()
    years = [str(r["fiscal_year"]) for r in rows]
    gm = [r.get("gross_margin") for r in rows]
    om = [r.get("operating_margin") for r in rows]
    nm = [r.get("net_margin") for r in rows]

    fig, ax = plt.subplots(figsize=(6.4, 3.0))
    ax.plot(years, gm, marker="o", label="Gross margin", color=_ACCENT)
    ax.plot(years, om, marker="s", label="Operating margin", color=_ACCENT2)
    ax.plot(years, nm, marker="^", label="Net margin", color="#5a7d9a")
    ax.set_ylabel("Margin (%)")
    ax.set_title("Profitability Margins by Fiscal Year", color=_ACCENT, fontweight="bold")
    ax.legend(frameon=False, fontsize=8)
    fig.tight_layout()
    path = str(Path(out_dir) / "chart_margins.png")
    fig.savefig(path, bbox_inches="tight")
    plt.close(fig)
    return path