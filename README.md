# Equity Research Swarm

A multi-agent system that turns a stock ticker into a **fully-sourced, fact-checked research brief**. Built with LangGraph. Every claim in the output is traceable to a retrieved source or a tool result, and a dedicated critic agent loops back any unsupported statement before it reaches the user.

> **Not investment advice.** This is an engineering demonstration. It produces research summaries, never buy/sell/hold recommendations.

---

## Why this exists

Generic LLMs answer finance questions fluently but unverifiably — and in finance, an invented number costs real money. This system is built around the one thing that makes AI usable for high-stakes work: **grounding you can check.**

- Every claim links to its source passage or tool output.
- A **critic agent** re-reads each draft and sends unsupported claims back for revision (the hallucination-catch loop).
- An **eval harness** scores groundedness so reliability is a number, not a vibe.
- **Least-privilege tools** (read-only) + a **human checkpoint** before the final brief — directly addressing the "excessive agency" failure mode (OWASP LLM06).

## The swarm

| Agent | Role |
|-------|------|
| Planner | Decomposes the request into research sub-questions |
| Retriever (RAG) | Hybrid search + rerank over a filings knowledge base; returns cited passages |
| Quant | Read-only financial-metric tools |
| Analyst | Drafts the brief — required to cite every claim |
| Critic / Validator | Flags any claim not backed by evidence; loops back for revision |
| Synthesizer | Final formatting + the not-advice guardrail |

## Run it (no keys needed)

```bash
pip install -r requirements.txt
python -m swarm.run --ticker DEMO          # runs entirely on bundled sample data
```

For live data and a real model, see `Configuration` below.

## Live mode (real tickers)

`DATA_MODE=live` pulls **real** filings from SEC EDGAR (keyless) and financial
metrics from FMP or Alpha Vantage (free key). Set keys in `.env`, then verify
the data layer in isolation before a full run:

```bash
DATA_MODE=live FMP_API_KEY=xxx SEC_USER_AGENT="Your Name you@email.com" \
    python -m swarm.tools.smoke_live AAPL
```

If both sources pass, run the swarm normally — it will use live data:

```bash
DATA_MODE=live python -m swarm.run --ticker AAPL --trace
```

Live fetches degrade gracefully: any network/quota/parse failure logs a warning
and falls back to bundled sample data rather than crashing the run.

## Configuration

Copy `.env.example` to `.env`:

| Variable | Default | Purpose |
|----------|---------|---------|
| `MODEL_PROVIDER` | `mock` | `mock` (no key, deterministic) / `groq` / `anthropic` / `openai` |
| `DATA_MODE` | `sample` | `sample` (bundled files) / `live` (EDGAR + yfinance) |
| `GROQ_API_KEY` | — | Free key from console.groq.com |

The model layer is swappable in one line — `mock` runs the whole graph offline so the evals are reproducible and the demo never breaks.

## Eval harness

```bash
python -m swarm.eval.run
```

Reports groundedness (share of claims backed by evidence) and the critic's hallucination-catch rate on bundled fixtures.

## Deploy (Hugging Face Spaces)

```bash
python -m swarm.web      # local Gradio UI at localhost:7860
```

Push the repo to a Gradio Space, add `GROQ_API_KEY` under Settings → Secrets, set `MODEL_PROVIDER=groq`. See `DEPLOY.md`.

## Architecture

See `docs/architecture.md`. Flow: ticker → planner → {retriever, quant} → analyst → critic ⟲ → human checkpoint → synthesizer.
