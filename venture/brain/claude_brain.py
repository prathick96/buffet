"""
venture/brain/claude_brain.py — the qualitative reasoning brain (local Claude Code CLI).

Drop-in for AnalystEngine(llm_brain=...). Given a MarketSnapshot it returns:
    {"sentiment": "BULLISH|BEARISH|NEUTRAL", "score": -1..1,
     "rationale": "<=2 sentences", "key_factors": [...]}

Runs the LOCAL `claude -p` CLI in headless mode — no API key, no API billing
(uses the machine's Claude Code auth). Calls are cached per (symbol, hour) so a
backtest/loop doesn't fire one ~30s call per bar.

A `persona` string lets the same brain play Bull vs. Bear in the debate graph.

License: original code, stdlib only -> commercial-clean.
"""
from __future__ import annotations

import json
import shutil
import subprocess
from datetime import datetime, timezone


class ClaudeBrain:
    def __init__(self, model: str = "sonnet", timeout: int = 180,
                 cli_path: str | None = None, persona: str = "ruthless but disciplined"):
        self.model = model
        self.timeout = timeout
        self.persona = persona
        self.cli_path = cli_path or shutil.which("claude") or "claude"
        self._cache: dict = {}

    def __call__(self, snap) -> dict:
        key = f"{self.persona}|{snap.symbol}|{datetime.now(timezone.utc):%Y%m%d_%H}"
        if key in self._cache:
            return self._cache[key]
        try:
            data = self._parse(self._call(self._prompt(snap)))
        except Exception as e:  # never crash the loop — degrade to neutral
            data = {"sentiment": "NEUTRAL", "score": 0.0,
                    "rationale": f"brain error: {e}", "key_factors": ["error"]}
        self._cache[key] = data
        return data

    # ------------------------------------------------------------------ prompt
    def _prompt(self, snap) -> str:
        news = "\n".join(f"- {n.get('title', '')}" for n in (snap.news or [])[:8]) \
            or "No recent news."
        ctx = "\n".join(snap.retrieved_context or []) or "No strategy context."
        ind = ", ".join(f"{k}={v}" for k, v in (snap.indicators or {}).items()) or "n/a"
        return (
            f"You are a {self.persona} quantitative trading analyst judging {snap.symbol}. "
            f"Be sharp, calculated, and money-focused; weigh evidence over headlines.\n\n"
            f"Price: {snap.price}\nIndicators: {ind}\n\nRecent news:\n{news}\n\n"
            f"Strategy/legend context:\n{ctx}\n\n"
            'Return ONLY a JSON object, no markdown:\n'
            '{"sentiment":"BULLISH|BEARISH|NEUTRAL","score":<float -1..1>,'
            '"rationale":"<=2 sentences citing specifics","key_factors":["f1","f2"]}'
        )

    # -------------------------------------------------------------------- call
    def _call(self, prompt: str) -> str:
        proc = subprocess.run(
            [self.cli_path, "-p", prompt, "--output-format", "text", "--model", self.model],
            input="", capture_output=True, text=True, timeout=self.timeout,
        )
        if proc.returncode != 0:
            raise RuntimeError(f"claude CLI exit {proc.returncode}: {proc.stderr.strip()[:200]}")
        return proc.stdout.strip()

    @staticmethod
    def _parse(raw: str) -> dict:
        if "```" in raw:
            raw = raw.split("```")[1]
            if raw.startswith("json"):
                raw = raw[4:]
        d = json.loads(raw)
        score = float(d.get("score", 0.0))
        return {
            "sentiment": d.get("sentiment", "NEUTRAL"),
            "score": max(-1.0, min(1.0, score)),
            "rationale": d.get("rationale", ""),
            "key_factors": list(d.get("key_factors", [])),
        }


def make_claude_brain(**kwargs) -> ClaudeBrain:
    """Convenience factory: `AnalystEngine(llm_brain=make_claude_brain())`."""
    return ClaudeBrain(**kwargs)


def bull_brain(**kwargs) -> ClaudeBrain:
    """An aggressive long-side advocate for the debate's Bull node."""
    return ClaudeBrain(persona="an aggressive, opportunistic BULL who builds the "
                       "strongest possible long case (still honest about real risks)", **kwargs)


def bear_brain(**kwargs) -> ClaudeBrain:
    """A skeptical short-seller for the debate's Bear node."""
    return ClaudeBrain(persona="a ruthless, skeptical BEAR / short-seller who hunts "
                       "every downside risk and overstretched valuation", **kwargs)
