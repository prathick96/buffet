"""
venture/rag/store.py — the shared knowledge store (the "RAG" in agentic RAG).

The Scout ingests news/web/fundamentals here; the Analyst retrieves relevant
context at decision time. `InMemoryKnowledgeStore` is a dependency-free keyword
retriever so the loop runs offline in tests. A `FaissKnowledgeStore` adapter
(wrapping the notebook's existing legends KB + sentence-transformers) lands in
Phase 1 behind this same interface.

License: original code, stdlib only -> commercial-clean.
"""
from __future__ import annotations

from typing import Protocol, runtime_checkable


@runtime_checkable
class KnowledgeStore(Protocol):
    def ingest(self, text: str, meta: dict | None = None) -> None: ...
    def retrieve(self, query: str, k: int = 3) -> list: ...


class InMemoryKnowledgeStore:
    """Offline keyword-overlap retrieval — stand-in for FAISS until Phase 1."""

    def __init__(self) -> None:
        self.docs: list = []   # list of (text, meta)
        self._seen: set = set()

    def ingest(self, text: str, meta: dict | None = None) -> None:
        if text and text.strip():
            t = text.strip()
            if t in self._seen:
                return
            self._seen.add(t)
            self.docs.append((t, meta or {}))

    def retrieve(self, query: str, k: int = 3) -> list:
        q = set(query.lower().split())
        scored = []
        for text, _meta in self.docs:
            overlap = len(q & set(text.lower().split()))
            if overlap:
                scored.append((overlap, text))
        if not scored:                       # no keyword hit -> recent news is the default context
            return [t for t, _ in reversed(self.docs[-k:])]
        scored.sort(key=lambda x: x[0], reverse=True)
        return [t for _, t in scored[:k]]

    def __len__(self) -> int:
        return len(self.docs)
