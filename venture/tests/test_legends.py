"""
venture/tests/test_legends.py — Trading Legends RAG seed.
Run:  python venture/tests/test_legends.py
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from rag.legends import TRADING_LEGENDS, legend_documents, load_legends  # noqa: E402
from rag.tfidf_store import TfidfKnowledgeStore  # noqa: E402


def test_legends_count():
    assert len(TRADING_LEGENDS) == 6 and len(legend_documents()) == 6
    print("PASS legends_count")


def test_legends_retrieval():
    kb = load_legends(TfidfKnowledgeStore())
    hits = kb.retrieve("intrinsic value moat wonderful companies fair price", k=1)
    assert hits and "Buffett" in hits[0]
    print(f"PASS legends_retrieval (top legend matched)")


if __name__ == "__main__":
    tests = [v for k, v in sorted(globals().items())
             if k.startswith("test_") and callable(v)]
    for fn in tests:
        fn()
    print(f"\nALL {len(tests)} LEGENDS TESTS PASSED")
