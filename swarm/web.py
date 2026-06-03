"""Gradio UI. Local: python -m app.web  (serves on :7860)
Deploy: push repo to a Hugging Face Gradio Space (see DEPLOY.md)."""
import gradio as gr
from .graph import run_swarm
from .config import CONFIG


def analyze(ticker: str):
    ticker = (ticker or "DEMO").strip().upper()
    state = run_swarm(ticker)

    brief = state["final"]
    sources = "\n".join(
        f"- `{e['id']}` — {e['source']}" for e in state["evidence"]
    )
    meta = (
        f"**Mode:** {CONFIG.model_provider} model / {CONFIG.data_mode} data  \n"
        f"**Critic revisions:** {state.get('revisions', 0)}  \n"
        f"**Evidence passages used:** {len(state['evidence'])}"
    )
    trace = state["tracer"].render()
    return brief, sources, meta, trace


DESCRIPTION = """
# Equity Research Swarm
A team of AI agents produces a **fully-sourced, fact-checked** research brief.
Every claim is traceable; a critic agent rejects anything unsupported before it ships.

*Engineering demo — not investment advice. Sample data ships with ticker `DEMO`.*
"""

with gr.Blocks(title="Equity Research Swarm") as demo:
    gr.Markdown(DESCRIPTION)
    with gr.Row():
        ticker_in = gr.Textbox(label="Ticker", value="DEMO", scale=4)
        go = gr.Button("Run swarm", variant="primary", scale=1)
    with gr.Row():
        with gr.Column(scale=3):
            brief_out = gr.Markdown(label="Research brief")
        with gr.Column(scale=2):
            meta_out = gr.Markdown(label="Run summary")
            sources_out = gr.Markdown(label="Sources")
    with gr.Accordion("Execution trace (decision log)", open=False):
        trace_out = gr.Code(label="trace", language=None)

    go.click(analyze, inputs=ticker_in,
             outputs=[brief_out, sources_out, meta_out, trace_out])

if __name__ == "__main__":
    demo.launch()
