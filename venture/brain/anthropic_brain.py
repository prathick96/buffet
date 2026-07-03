"""
venture/brain/anthropic_brain.py — cloud LLM brain via the Anthropic API.

Drop-in replacement for the local ClaudeBrain (same callable interface), for when
the app runs on a server where the local `claude` CLI isn't available. Reads the
key through the secrets layer (env -> .env -> vault); model is configurable.

    from brain.anthropic_brain import AnthropicBrain
    analyst = AnalystEngine(llm_brain=AnthropicBrain())

Default model is claude-opus-4-8 (Anthropic's guidance). Override with the
ANTHROPIC_MODEL env var — e.g. claude-sonnet-5 or claude-haiku-4-5 to cut cost
(sensible for a tiny paper portfolio; see BLUEPRINT cost note).

License: original code; anthropic SDK (MIT) -> commercial-clean.
"""
from __future__ import annotations

import json
import re
from datetime import datetime, timezone

from security.secrets import get_secret, require_secret

DEFAULT_MODEL = "claude-opus-4-8"


class AnthropicBrain:
    def __init__(self, model: str | None = None, max_tokens: int = 600,
                 persona: str = "ruthless but disciplined", timeout: int = 60):
        self.persona = persona
        self.max_tokens = max_tokens
        self.model = model or get_secret("ANTHROPIC_MODEL", default=DEFAULT_MODEL)
        self.timeout = timeout
        self._cache: dict = {}
        self._client = None

    # -------------------------------------------------------------- interface
    def __call__(self, snap) -> dict:
        key = f"{self.persona}|{snap.symbol}|{datetime.now(timezone.utc):%Y%m%d_%H}"
        if key in self._cache:
            return self._cache[key]
        try:
            data = self._parse(self._call(snap))
        except Exception as e:                       # never crash the loop
            data = {"sentiment": "NEUTRAL", "score": 0.0,
                    "rationale": f"brain error: {e}", "key_factors": ["error"]}
        self._cache[key] = data
        return data

    # ------------------------------------------------------------------ client
    def _get_client(self):
        if self._client is None:
            import anthropic  # lazy
            self._client = anthropic.Anthropic(
                api_key=require_secret("ANTHROPIC_API_KEY"), timeout=self.timeout)
        return self._client

    # ------------------------------------------------------------------ prompt
    def _system(self) -> str:
        return (
            f"You are a {self.persona} quantitative trading analyst. Weigh evidence over "
            "headlines; be sharp and calculated. Respond with ONLY a JSON object, no "
            "markdown fences, matching exactly: "
            '{"sentiment":"BULLISH|BEARISH|NEUTRAL","score":<float -1..1>,'
            '"rationale":"<=2 sentences citing specifics","key_factors":["f1","f2"]}')

    def _user(self, snap) -> str:
        news = "\n".join(f"- {n.get('title', '')}" for n in (snap.news or [])[:8]) \
            or "No recent news."
        ctx = "\n".join(snap.retrieved_context or []) or "No strategy context."
        ind = ", ".join(f"{k}={v}" for k, v in (snap.indicators or {}).items()) or "n/a"
        return (f"Judge {snap.symbol}. Price: {snap.price}\nIndicators: {ind}\n\n"
                f"Recent news:\n{news}\n\nStrategy/legend context:\n{ctx}")

    def _call(self, snap) -> str:
        client = self._get_client()
        resp = client.messages.create(
            model=self.model,
            max_tokens=self.max_tokens,
            # Stable instruction prefix is cache-eligible (kicks in once the prefix
            # is large enough — e.g. when the legends KB is folded in here later).
            system=[{"type": "text", "text": self._system(),
                     "cache_control": {"type": "ephemeral"}}],
            messages=[{"role": "user", "content": self._user(snap)}],
        )
        return "".join(b.text for b in resp.content
                       if getattr(b, "type", None) == "text").strip()

    # ------------------------------------------------------------------- parse
    @staticmethod
    def _parse(raw: str) -> dict:
        if "```" in raw:
            raw = raw.split("```")[1]
            if raw.startswith("json"):
                raw = raw[4:]
        raw = raw.strip()
        try:
            d = json.loads(raw)
        except Exception:
            m = re.search(r"\{.*\}", raw, re.DOTALL)      # find first JSON object
            d = json.loads(m.group(0)) if m else {}
        score = float(d.get("score", 0.0))
        return {
            "sentiment": d.get("sentiment", "NEUTRAL"),
            "score": max(-1.0, min(1.0, score)),
            "rationale": d.get("rationale", ""),
            "key_factors": list(d.get("key_factors", [])),
        }


def anthropic_bull_brain(**kw) -> AnthropicBrain:
    return AnthropicBrain(persona="an aggressive, opportunistic BULL building the "
                          "strongest possible long case (still honest about risks)", **kw)


def anthropic_bear_brain(**kw) -> AnthropicBrain:
    return AnthropicBrain(persona="a ruthless, skeptical BEAR / short-seller hunting "
                          "every downside risk", **kw)
