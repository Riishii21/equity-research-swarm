# Deploying to Hugging Face Spaces

This gets you a public, clickable demo URL. Free tier is enough.

## 1. Create the Space
1. Go to huggingface.co → **New** → **Space**.
2. Name it (e.g. `equity-research-swarm`), pick **Gradio** as the SDK, **Public**.

## 2. Add the entrypoint Spaces expects
Spaces runs `app.py` at the repo root. This repo's UI lives in `app/web.py`,
so add a tiny root shim named `app.py`:

```python
from swarm.web import demo
demo.launch()
```

(Already included in this repo as `app.py`.)

## 3. Push the code
```bash
git init
git remote add origin https://huggingface.co/spaces/<your-username>/equity-research-swarm
git add .
git commit -m "Equity research swarm"
git push origin main
```

## 4. Choose how it runs
The Space builds from `requirements.txt` automatically.

- **Zero-cost demo (recommended to start):** leave `MODEL_PROVIDER=mock`.
  It runs the full swarm deterministically with no API calls — nothing to pay for,
  nothing to break. Reviewers see the agents, the citations, the trace, the eval logic.

- **Live model:** in **Settings → Variables and secrets**:
  - add secret `GROQ_API_KEY` (free key from console.groq.com)
  - add variable `MODEL_PROVIDER=groq`
  - add the optional dep: uncomment `langchain-groq` in `requirements.txt`

  Groq has a generous free tier. To cap exposure, keep the Space mock-by-default
  and only flip to `groq` when you want to show best-quality output.

## A note on cost and safety
A public URL on a paid model means strangers can spend your quota. Mitigations:
keep `mock` as the default, or gate the Space behind Hugging Face's private/
password setting and share selectively with reviewers.

## Live financial data (optional, not for Spaces free tier)
`DATA_MODE=live` pulls from SEC EDGAR + yfinance. Needs the optional deps and
outbound network. Test locally first; it is intentionally stubbed in `sample` mode.
