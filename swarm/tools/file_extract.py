"""Extract analyzable text from uploaded documents (PDF, Excel, CSV).
Text-extraction only by design — agents read and cite the text.
"""
from __future__ import annotations
import os
import subprocess
from pathlib import Path


class UploadError(RuntimeError):
    pass


def _chunk_pages(text: str, source: str, prefix: str) -> list[dict]:
    segs, buf, n = [], [], 0
    for para in text.split("\n\n"):
        buf.append(para)
        n += len(para)
        if n > 3000:
            segs.append("\n\n".join(buf)); buf, n = [], 0
    if buf:
        segs.append("\n\n".join(buf))
    return [{"id": f"{prefix}-{i}", "source": source, "text": s.strip()}
            for i, s in enumerate(segs) if s.strip()]


def _extract_pdf(path: str, name: str) -> list[dict]:
    try:
        out = subprocess.run(["pdftotext", "-layout", path, "-"],
                             capture_output=True, text=True, timeout=60)
    except (subprocess.TimeoutExpired, FileNotFoundError) as e:
        raise UploadError(f"PDF text extraction failed: {e}")
    text = out.stdout or ""
    if len(text.strip()) < 200:
        raise UploadError(
            "Could not extract readable text — the PDF may be scanned/image-based. "
            "Try a text-based PDF or an Excel file.")
    return _chunk_pages(text, f"{name} (uploaded PDF)", "doc")


def _extract_excel(path: str, name: str) -> list[dict]:
    import pandas as pd
    try:
        sheets = pd.read_excel(path, sheet_name=None, header=None)
    except Exception as e:
        raise UploadError(f"Could not read spreadsheet: {e}")
    docs = []
    for i, (sheet_name, df) in enumerate(sheets.items()):
        if df.empty:
            continue
        text = df.to_string(index=False, na_rep="")
        docs.append({"id": f"sheet-{i}", "source": f"{name} · sheet '{sheet_name}' (uploaded)",
                     "text": text[:12000]})
    if not docs:
        raise UploadError("Spreadsheet appears empty.")
    return docs


def _extract_csv(path: str, name: str) -> list[dict]:
    import pandas as pd
    try:
        df = pd.read_csv(path, header=None)
    except Exception as e:
        raise UploadError(f"Could not read CSV: {e}")
    if df.empty:
        raise UploadError("CSV appears empty.")
    return [{"id": "csv-0", "source": f"{name} (uploaded CSV)",
             "text": df.to_string(index=False, na_rep="")[:12000]}]


def extract_document(path: str, original_name: str | None = None) -> dict:
    name = original_name or os.path.basename(path)
    stem = Path(name).stem.replace("_", " ").replace("-", " ").strip()
    ext = Path(name).suffix.lower()
    if ext == ".pdf":
        docs = _extract_pdf(path, name)
    elif ext in (".xlsx", ".xls", ".xlsm"):
        docs = _extract_excel(path, name)
    elif ext in (".csv", ".tsv"):
        docs = _extract_csv(path, name)
    else:
        raise UploadError(f"Unsupported file type '{ext}'. Upload a PDF, Excel, or CSV.")
    return {"company": stem or "Uploaded Document", "documents": docs}