# Architecture

## Flow

```
ticker
  └─> planner          decomposes into research sub-questions
        └─> gather     retriever (RAG, hybrid search) + quant (read-only tools)
              └─> analyst    drafts brief, every claim tagged [src:...]
                    └─> critic    audits citations
                          ├─ unsupported? ──> back to analyst  (loop, max N)
                          └─ clean? ──> human checkpoint ──> synthesizer ──> brief
```

Built on **LangGraph** specifically for the critic→analyst cycle. A linear
chain (or CrewAI's sequential model) can't express "loop back until valid"
without bolting on external control flow; LangGraph's conditional edges model
it natively. That cycle is the project's defining feature.

## Modules

| Path | Responsibility |
|------|----------------|
| `swarm/graph.py` | State schema, all agent nodes, the LangGraph wiring + critic loop |
| `swarm/model.py` | Provider-agnostic LLM interface (mock / groq / anthropic / openai) |
| `swarm/rag/retriever.py` | Chunking + hybrid BM25/TF-IDF retrieval, optional dense embeddings |
| `swarm/tools/quant.py` | Read-only metric tools (least-privilege allowlist) |
| `swarm/observability/tracer.py` | Per-step execution + timing log |
| `swarm/eval/run.py` | Groundedness + critic catch-rate metrics |
| `swarm/web.py` | Gradio UI |
| `swarm/config.py` | All runtime switches (env-driven) |

## Design decisions that signal seniority

1. **Grounding is enforced, not requested.** The critic mechanically rejects
   any claim without a valid `[src:]` tag — hallucination defense as control
   flow, not a polite prompt.

2. **Least-privilege tools.** The tool allowlist contains only readers. There
   is no code path that can trade, transfer, or mutate — the LLM06 "excessive
   agency" mitigation, made auditable (`test_tools_are_read_only`).

3. **Human-in-the-loop checkpoint** before the final brief is emitted.

4. **Reproducible evals.** Mock mode is deterministic, so groundedness and
   catch-rate are stable numbers a reviewer can re-run and verify.

5. **Swappable everything.** Model provider, data source, and embedding engine
   are one-line config switches — the system isn't welded to any vendor.
