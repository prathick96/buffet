"""
venture/billing/pricing.py — model pricing + exact token->USD cost.

Rates are $ per 1,000,000 tokens (Anthropic list pricing). Cost is computed from
the API response's own `usage` object — the same tokens Anthropic bills on — so
our number matches the console to the token.

cache_read  = 0.1x uncached-input;  cache_write(5m) = 1.25x uncached-input.

License: original code, stdlib only -> commercial-clean.
"""
from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Rate:
    inp: float          # $/MTok uncached input
    out: float          # $/MTok output
    cache_read: float   # $/MTok cache read
    cache_write: float  # $/MTok cache write (5-min ephemeral)


# $/MTok. Verified against the claude-api pricing table (2026-06).
PRICING = {
    "claude-opus-4-8":  Rate(5.0, 25.0, 0.50, 6.25),
    "claude-opus-4-7":  Rate(5.0, 25.0, 0.50, 6.25),
    "claude-sonnet-5":  Rate(3.0, 15.0, 0.30, 3.75),   # list; intro $2/$10 to 2026-08-31
    "claude-sonnet-4-6": Rate(3.0, 15.0, 0.30, 3.75),
    "claude-haiku-4-5": Rate(1.0, 5.0, 0.10, 1.25),
    "claude-fable-5":   Rate(10.0, 50.0, 1.00, 12.50),
}


def cost_usd(model: str, input_tokens: int = 0, output_tokens: int = 0,
             cache_read_tokens: int = 0, cache_write_tokens: int = 0) -> float:
    r = PRICING.get(model)
    if r is None:
        return 0.0
    return (input_tokens * r.inp + output_tokens * r.out
            + cache_read_tokens * r.cache_read
            + cache_write_tokens * r.cache_write) / 1_000_000.0


def usage_to_cost(model: str, usage) -> tuple[dict, float]:
    """Normalize an Anthropic `usage` (object or dict) -> (token dict, USD cost)."""
    def g(name: str) -> int:
        v = usage.get(name) if isinstance(usage, dict) else getattr(usage, name, None)
        return int(v or 0)

    tokens = {
        "input_tokens": g("input_tokens"),
        "output_tokens": g("output_tokens"),
        "cache_read_input_tokens": g("cache_read_input_tokens"),
        "cache_creation_input_tokens": g("cache_creation_input_tokens"),
    }
    cost = cost_usd(model, tokens["input_tokens"], tokens["output_tokens"],
                    tokens["cache_read_input_tokens"], tokens["cache_creation_input_tokens"])
    return tokens, cost
