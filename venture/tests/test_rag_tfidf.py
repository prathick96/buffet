"""
venture/tests/test_rag_tfidf.py — TF-IDF retrieval ranking + dedupe.
Run:  python venture/tests/test_rag_tfidf.py
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from rag.tfidf_store import TfidfKnowledgeStore  # noqa: E402


def test_ranks_relevant_doc_first():
    s = TfidfKnowledgeStore()
    s.ingest("Bitcoin ETF inflows surge to record high")
    s.ingest("Apple unveils new iPhone lineup")
    s.ingest("Ethereum network upgrade improves scalability")
    hits = s.retrieve("bitcoin etf inflows record", k=2)
    assert hits, "no retrieval"
    assert "Bitcoin ETF" in hits[0], hits
    print(f"PASS ranks_relevant_doc_first (top='{hits[0]}')")


def test_dedupe():
    s = TfidfKnowledgeStore()
    s.ingest("same headline")
    s.ingest("same headline")
    assert len(s) == 1
    print("PASS dedupe")


if __name__ == "__main__":
    tests = [v for k, v in sorted(globals().items())
             if k.startswith("test_") and callable(v)]
    for fn in tests:
        fn()
    print(f"\nALL {len(tests)} TFIDF-RAG TESTS PASSED")
