"""Retrieval pipeline.

Default engine is lexical hybrid (BM25 + TF-IDF cosine) — fully offline, no
downloads, deterministic. Set RAG_EMBEDDINGS=real to swap in sentence-transformer
dense embeddings as an upgrade (requires the optional dependency).

Boilerplate (cover pages, TOC, legalese) is filtered before indexing, and a
small substance boost steers retrieval toward analysis-relevant prose.
"""
from __future__ import annotations
import json
import re
from dataclasses import dataclass
from pathlib import Path

from rank_bm25 import BM25Okapi
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity

from ..config import CONFIG

_DATA = Path(__file__).resolve().parent.parent / "data" / "filings"


@dataclass
class Passage:
    id: str
    source: str
    text: str
    score: float = 0.0
    substance: float = 0.0


def _tokenize(s: str) -> list[str]:
    return re.findall(r"[a-z0-9]+", s.lower())


_BOILERPLATE = (
    "indicate by check mark",
    "regulation s-t",
    "securities exchange act of 1934",
    "table of contents",
    "i.r.s. employer",
    "irs employer",
    "emerging growth company",
    "smaller reporting company",
    "accelerated filer",
    "preceding 12 months",
    "filing requirements",
    "registrant",
    "commission file number",
    "title of each class",
    "trading symbol",
    "mine safety disclosures",
    "exhibit",
)

_SUBSTANCE = (
    "increased", "decreased", "growth", "margin", "revenue", "net sales",
    "compared to", "year-over-year", "driven by", "risk", "competition",
    "demand", "guidance", "outlook", "gross margin", "operating", "decline",
    "results of operations", "management", "macroeconomic",
)


def _is_boilerplate(text: str) -> bool:
    low = text.lower()
    hits = sum(1 for p in _BOILERPLATE if p in low)
    sentence_density = low.count(". ") / (len(low.split()) + 1)
    return hits >= 2 and sentence_density < 0.03


def _substance_score(text: str) -> float:
    low = text.lower()
    return sum(1 for t in _SUBSTANCE if t in low)


def _chunk(text: str, size: int = 60, overlap: int = 15) -> list[str]:
    """Word-window chunking with overlap. Small windows because filing
    passages are dense; overlap preserves cross-boundary context."""
    words = text.split()
    if len(words) <= size:
        return [text]
    chunks, i = [], 0
    while i < len(words):
        chunks.append(" ".join(words[i:i + size]))
        i += size - overlap
    return chunks


class Retriever:
    def __init__(self, ticker: str = "DEMO", documents: dict | None = None):
        self.passages: list[Passage] = []
        self.company: str = ""
        if documents is not None:
            self._ingest(documents)
        else:
            self._load(ticker)
        self._build_index()

    def _load(self, ticker: str):
        if CONFIG.data_mode == "live":
            from .live_filings import fetch_live_filings, LiveDataError
            try:
                data = fetch_live_filings(ticker)
                self._ingest(data)
                return
            except LiveDataError as e:
                print(f"[warn] live filings failed ({e}); falling back to sample data")
        path = _DATA / f"{ticker.lower()}.json"
        if not path.exists():
            path = _DATA / "demo.json"
        data = json.loads(path.read_text())
        self._ingest(data)

    def _ingest(self, data: dict):
        self.company = data.get("company", "")
        kept, dropped = [], 0
        for doc in data["documents"]:
            for j, chunk in enumerate(_chunk(doc["text"])):
                if _is_boilerplate(chunk):
                    dropped += 1
                    continue
                kept.append(
                    Passage(id=f"{doc['id']}#{j}", source=doc["source"],
                            text=chunk, substance=_substance_score(chunk))
                )
        if not kept:
            for doc in data["documents"]:
                for j, chunk in enumerate(_chunk(doc["text"])):
                    kept.append(Passage(id=f"{doc['id']}#{j}", source=doc["source"],
                                        text=chunk, substance=_substance_score(chunk)))
        self.passages.extend(kept)

    def _build_index(self):
        corpus = [p.text for p in self.passages]
        self._bm25 = BM25Okapi([_tokenize(c) for c in corpus])
        self._tfidf = TfidfVectorizer().fit(corpus)
        self._tfidf_matrix = self._tfidf.transform(corpus)
        self._dense = None
        if CONFIG.rag_embeddings == "real":
            self._init_dense(corpus)

    def _init_dense(self, corpus: list[str]):
        try:
            from sentence_transformers import SentenceTransformer
            self._embedder = SentenceTransformer("all-MiniLM-L6-v2")
            self._dense = self._embedder.encode(corpus, normalize_embeddings=True)
            print(f"[rag] semantic embeddings active ({len(corpus)} chunks encoded)")
        except Exception as e:
            print(f"[warn] embeddings unavailable ({e}); using lexical retrieval only")
            self._dense = None

    def _hybrid_scores(self, query: str):
        bm = self._bm25.get_scores(_tokenize(query))
        bm = bm / (bm.max() + 1e-9)
        qv = self._tfidf.transform([query])
        tf = cosine_similarity(qv, self._tfidf_matrix)[0]
        if self._dense is not None:
            import numpy as np
            qd = self._embedder.encode([query], normalize_embeddings=True)
            dense = (self._dense @ qd[0])
            return 0.4 * bm + 0.3 * tf + 0.3 * dense
        return 0.6 * bm + 0.4 * tf

    def retrieve(self, query: str, k: int = 3) -> list[Passage]:
        scores = self._hybrid_scores(query)
        max_sub = max((p.substance for p in self.passages), default=0) or 1
        ranked = sorted(
            (
                (p, s + 0.15 * (p.substance / max_sub))
                for p, s in zip(self.passages, scores)
            ),
            key=lambda x: x[1], reverse=True,
        )
        out = []
        for p, s in ranked[:k]:
            out.append(Passage(id=p.id, source=p.source, text=p.text,
                               score=float(s), substance=p.substance))
        return out