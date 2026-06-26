"""
venture/rag/faiss_store.py — semantic RAG via sentence-transformers + FAISS.

Same KnowledgeStore interface as the in-memory / TF-IDF stores, but with true
semantic retrieval. Heavy deps (torch), so imported lazily and only used once
`pip install sentence-transformers faiss-cpu` is done (both permissive: Apache/MIT).
A `FaissKnowledgeStore.load_legends_kb(...)` wraps the notebook's existing FAISS
legends KB later.

License: original code; sentence-transformers (Apache-2), faiss (MIT) -> commercial-clean.
"""
from __future__ import annotations


class FaissKnowledgeStore:
    def __init__(self, model_name: str = "sentence-transformers/all-MiniLM-L6-v2"):
        from sentence_transformers import SentenceTransformer  # lazy, heavy
        import faiss  # noqa: F401
        self._model = SentenceTransformer(model_name)
        self._faiss = faiss
        self._index = None
        self._dim = self._model.get_sentence_embedding_dimension()
        self.docs: list = []
        self._seen: set = set()

    def _embed(self, texts: list):
        import numpy as np
        v = self._model.encode(texts, normalize_embeddings=True)
        return np.asarray(v, dtype="float32")

    def ingest(self, text: str, meta: dict | None = None) -> None:
        if not text or not text.strip():
            return
        t = text.strip()
        if t in self._seen:
            return
        self._seen.add(t)
        self.docs.append((t, meta or {}))
        vec = self._embed([t])
        if self._index is None:
            self._index = self._faiss.IndexFlatIP(self._dim)   # cosine via normalized IP
        self._index.add(vec)

    def retrieve(self, query: str, k: int = 3) -> list:
        if not self.docs or self._index is None:
            return []
        k = min(k, len(self.docs))
        _scores, idx = self._index.search(self._embed([query]), k)
        return [self.docs[i][0] for i in idx[0] if 0 <= i < len(self.docs)]

    def __len__(self) -> int:
        return len(self.docs)
