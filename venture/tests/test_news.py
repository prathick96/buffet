"""
venture/tests/test_news.py — deterministic RSS parsing (no network).
Run:  python venture/tests/test_news.py
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from news.providers import RSSNewsProvider, parse_rss  # noqa: E402

SAMPLE = b"""<?xml version="1.0"?><rss version="2.0"><channel>
<title>Feed</title>
<item><title>Bitcoin surges past resistance</title>
<description>&lt;p&gt;Big &lt;b&gt;rally&lt;/b&gt; today&lt;/p&gt;</description>
<link>http://x/1</link></item>
<item><title>ETH upgrade ships</title>
<description>Network news</description><link>http://x/2</link></item>
</channel></rss>"""


def test_parse_rss_extracts_and_strips_html():
    items = parse_rss(SAMPLE, source="test")
    assert len(items) == 2
    assert items[0]["title"] == "Bitcoin surges past resistance"
    assert "<" not in items[0]["summary"] and "rally" in items[0]["summary"]
    assert items[0]["source"] == "test"
    print("PASS parse_rss_extracts_and_strips_html")


def test_feeds_for_routing():
    p = RSSNewsProvider()
    assert p._feeds_for("BTC/USDT") == p.crypto_feeds                # crypto -> crypto feeds
    assert p._feeds_for("AAPL") == [p.equity_tmpl.format(ticker="AAPL")]  # equity -> yahoo
    print("PASS feeds_for_routing")


if __name__ == "__main__":
    tests = [v for k, v in sorted(globals().items())
             if k.startswith("test_") and callable(v)]
    for fn in tests:
        fn()
    print(f"\nALL {len(tests)} NEWS TESTS PASSED")
