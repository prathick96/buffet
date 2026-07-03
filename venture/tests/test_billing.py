"""
venture/tests/test_billing.py — pricing, usage tracking, monthly budget guard.
Run:  python venture/tests/test_billing.py
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from billing.pricing import cost_usd, usage_to_cost  # noqa: E402
from billing.tracker import BudgetGuard, UsageTracker, month_to_date  # noqa: E402
from persistence.journal import Journal  # noqa: E402


class FakeUsage:
    def __init__(self, i, o, cr=0, cw=0):
        self.input_tokens = i
        self.output_tokens = o
        self.cache_read_input_tokens = cr
        self.cache_creation_input_tokens = cw


def test_cost_math_opus():
    # 1000 in, 500 out on Opus 4.8: 1000/1e6*5 + 500/1e6*25 = 0.0175
    assert abs(cost_usd("claude-opus-4-8", 1000, 500) - 0.0175) < 1e-12
    print("PASS cost_math_opus")


def test_usage_to_cost_object_and_dict_agree():
    t1, c1 = usage_to_cost("claude-opus-4-8", FakeUsage(1000, 500))
    t2, c2 = usage_to_cost("claude-opus-4-8", {"input_tokens": 1000, "output_tokens": 500})
    assert t1["input_tokens"] == 1000 and abs(c1 - c2) < 1e-12
    print("PASS usage_to_cost_object_and_dict_agree")


def test_unknown_model_costs_zero():
    assert cost_usd("some-other-model", 1000, 500) == 0.0
    print("PASS unknown_model_costs_zero")


def test_tracker_records_and_month_to_date():
    j = Journal(":memory:")
    tr = UsageTracker(j)
    tr.record("claude-opus-4-8", FakeUsage(1000, 500), symbol="AAPL")
    tr.record("claude-opus-4-8", FakeUsage(2000, 1000), symbol="NVDA")
    mtd = month_to_date(j)
    assert mtd["calls"] == 2
    assert abs(mtd["cost_usd"] - (0.0175 + 0.035)) < 1e-6
    assert mtd["input_tokens"] == 3000 and mtd["output_tokens"] == 1500
    j.close()
    print("PASS tracker_records_and_month_to_date")


def test_budget_guard_blocks_over_cap():
    j = Journal(":memory:")
    tr = UsageTracker(j)
    g = BudgetGuard(j, monthly_cap_usd=0.05)
    assert g.allow()                                   # nothing spent yet
    tr.record("claude-opus-4-8", FakeUsage(1000, 500))  # $0.0175
    assert g.allow() and abs(g.remaining() - (0.05 - 0.0175)) < 1e-6
    tr.record("claude-opus-4-8", FakeUsage(2000, 1000))  # +$0.035 -> $0.0525 > cap
    assert not g.allow() and g.remaining() == 0.0
    j.close()
    print("PASS budget_guard_blocks_over_cap")


def test_budget_disabled_is_unlimited():
    j = Journal(":memory:")
    g = BudgetGuard(j, 0)
    assert g.allow() and g.remaining() == float("inf")
    j.close()
    print("PASS budget_disabled_is_unlimited")


if __name__ == "__main__":
    tests = [v for k, v in sorted(globals().items())
             if k.startswith("test_") and callable(v)]
    for fn in tests:
        fn()
    print(f"\nALL {len(tests)} BILLING TESTS PASSED")
