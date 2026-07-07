"""
venture/security/secrets.py — the ONE way venture code reads secrets.

Precedence:  real environment variable  >  .env file  >  encrypted vault.
Never hardcode a secret anywhere — call get_secret()/require_secret() instead.

    from security.secrets import require_secret
    key = require_secret("ALPACA_API_KEY")        # raises if missing

License: original code, stdlib only -> commercial-clean.
"""
from __future__ import annotations

import os
from pathlib import Path

_dotenv_cache: dict = {}


class MissingSecret(Exception):
    """A required secret was not found in env, .env, or vault."""


def _parse_dotenv(path: str) -> dict:
    out: dict = {}
    p = Path(path)
    if not p.exists():
        return out
    for line in p.read_text(encoding="utf-8").splitlines():
        s = line.strip()
        if not s or s.startswith("#") or "=" not in s:
            continue
        k, v = s.split("=", 1)
        v = v.strip()
        if len(v) >= 2 and v[0] in "\"'" and v[-1] == v[0]:
            v = v[1:-1]                       # quoted value -> keep contents verbatim
        else:                                 # unquoted -> drop any inline "# comment"
            for sep in (" #", "\t#"):
                i = v.find(sep)
                if i != -1:
                    v = v[:i]
            v = v.strip().strip('"').strip("'")
        out[k.strip()] = v
    return out


def get_secret(name: str, default=None, vault=None, dotenv_path: str | None = None):
    """Resolve a secret by precedence: env var -> .env -> vault -> default."""
    if os.environ.get(name):
        return os.environ[name]
    path = dotenv_path or os.environ.get("VENTURE_DOTENV", ".env")
    if path not in _dotenv_cache:
        _dotenv_cache[path] = _parse_dotenv(path)
    if _dotenv_cache[path].get(name):
        return _dotenv_cache[path][name]
    if vault is not None:
        v = vault.get(name)
        if v:
            return v
    return default


def get_secret_clean(name: str, default=None, **kw):
    """get_secret() with any inline '# comment' stripped from the value.

    For config-style secrets (a model id, a dollar budget) that must never carry
    a trailing comment even if one leaks in from a .env template OR a pasted
    GitHub Actions secret — a commented model id silently breaks every API call,
    and a commented number crashes float()."""
    v = get_secret(name, default=default, **kw)
    if isinstance(v, str):
        for sep in (" #", "\t#"):
            i = v.find(sep)
            if i != -1:
                v = v[:i]
        v = v.strip()
    return v if v not in ("", None) else default


def require_secret(name: str, vault=None, dotenv_path: str | None = None) -> str:
    val = get_secret(name, vault=vault, dotenv_path=dotenv_path)
    if not val:
        raise MissingSecret(
            f"Required secret '{name}' not found. Set it as an env var, in .env, "
            f"or in the vault. See .env.example / SECURITY.md.")
    return val
