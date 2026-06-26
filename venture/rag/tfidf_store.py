"""
venture/rag/tfidf_store.py — upgraded RAG retrieval (TF-IDF cosine, stdlib only).

A real step up from keyword-overlap: ranks ingested news/strategy docs by TF-IDF
cosine similarity to the query. No torch, no faiss, no network -> commercial-clean
and runs anywhere. Swap to FaissKnowledgeStore (semantic embeddings) when
sentence-transformers is available; same interface either way.

License: original code, stdlib only -> commercial-clean.
"""
from __future__ import annotations

import math
from collections import Counter


def _tokenize(text: str) -> list:
    cleaned = "".join(c.lower() if c.isalnum() else " " for c in text)
    return [w for w in cleaned.split() if len(w) > 2]


class TfidfKnowledgeStore:
    def __init__(self) -> None:
        self.docs: list = []        # (text, meta)
        self._toks: list = []       # tokenized docs
        self._seen: set = set()     # dedupe identical text

    def ingest(self, text: str, meta: dict | None = None) -> None:
        if not text or not text.strip():
            return
        t = text.strip()
        if t in self._seen:
            return
        self._seen.add(t)
        self.docs.append((t, meta or {}))
        self._toks.append(_tokenize(t))

    def retrieve(self, query: str, k: int = 3) -> list:
        if not self.docs:
            return []
        n = len(self.docs)
        df = Counter()
        for toks in self._toks:
            for w in set(toks):
                df[w] += 1

        def vec(toks: list) -> dict:
            if not toks:
                return {}
            tf = Counter(toks)
            length = len(toks)
            return {w: (c / length) * (math.log((1 + n) / (1 + df.get(w, 0))) + 1)
                    for w, c in tf.items()}

        qv = vec(_tokenize(query))
        scores = []
        for i, toks in enumerate(self._toks):
            scores.append((self._cosine(qv, vec(toks)), i))
        scores.sort(key=lambda x: x[0], reverse=True)
        hits = [self.docs[i][0] for s, i in scores[:k] if s > 0]
        if hits:
            return hits
        return [t for t, _ in self.docs[-k:][::-1]]   # recency fallback

    @staticmethod
    def _cosine(a: dict, b: dict) -> float:
        if not a or not b:
            return 0.0
        common = set(a) & set(b)
        num = sum(a[w] * b[w] for w in common)
        da = math.sqrt(sum(x * x for x in a.values()))
        db = math.sqrt(sum(x * x for x in b.values()))
        return num / (da * db) if da and db else 0.0

    def __len__(self) -> int:
        return len(self.docs)
