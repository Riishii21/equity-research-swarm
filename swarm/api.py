"""FastAPI app: SSE streaming + PDF export, serving the UI."""
from __future__ import annotations
import json
import os
import tempfile
import uuid as _uuid

from fastapi import FastAPI, UploadFile, File, Form
from fastapi.responses import StreamingResponse, HTMLResponse, FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from .stream import run_swarm_streaming
from .graph import run_swarm
from .export.pdf_export import export_pdf
from .tools.file_extract import extract_document, UploadError

app = FastAPI(title="Equity Research Swarm")

_HERE = os.path.dirname(__file__)
_WEB = os.path.join(_HERE, "webui")
_UPLOADS: dict[str, dict] = {}  # token -> {"docs": {...}, "ticker": str}


@app.get("/", response_class=HTMLResponse)
def index():
    with open(os.path.join(_WEB, "index.html"), encoding="utf-8") as f:
        return f.read()


@app.post("/api/upload")
async def upload(file: UploadFile = File(...), ticker: str = Form("")):
    suffix = os.path.splitext(file.filename or "")[1]
    tmp = os.path.join(tempfile.mkdtemp(prefix="ers_up_"), f"upload{suffix}")
    with open(tmp, "wb") as f:
        f.write(await file.read())
    try:
        docs = extract_document(tmp, file.filename)
    except UploadError as e:
        return JSONResponse({"error": str(e)}, status_code=400)
    token = _uuid.uuid4().hex
    _UPLOADS[token] = {"docs": docs, "ticker": (ticker or "").strip().upper()}
    return {"token": token, "company": docs.get("company", ""),
            "chunks": len(docs.get("documents", []))}


@app.get("/api/stream_upload/{token}")
def stream_upload(token: str):
    entry = _UPLOADS.get(token)

    def gen():
        if not entry:
            yield f"data: {json.dumps({'stage':'error','status':'error','label':'Upload expired - please re-upload.'})}\n\n"
            return
        for event in run_swarm_streaming(entry["ticker"], uploaded_docs=entry["docs"]):
            payload = {k: v for k, v in event.items() if k != "_state_ref"}
            yield f"data: {json.dumps(payload)}\n\n"
    return StreamingResponse(gen(), media_type="text/event-stream",
                             headers={"Cache-Control": "no-cache",
                                      "X-Accel-Buffering": "no"})

class PdfRequest(BaseModel):
    ticker: str


@app.post("/api/pdf")
def pdf(req: PdfRequest):
    state = run_swarm(req.ticker)
    out = os.path.join(tempfile.mkdtemp(prefix="ers_pdf_"),
                       f"{req.ticker.upper()}_research_memo.pdf")
    export_pdf(state, out)
    return FileResponse(out, media_type="application/pdf",
                        filename=os.path.basename(out))