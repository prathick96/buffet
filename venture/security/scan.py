"""
venture/security/scan.py — lightweight secret scanner (recurrence guard).

Used by the pre-commit hook to block commits that contain likely secrets.
Stdlib only — no gitleaks dependency required.

    python venture/security/scan.py --staged        # scan git-staged files
    python venture/security/scan.py file1 file2 ...  # scan specific files
"""
from __future__ import annotations

import re
import subprocess
import sys

# (label, compiled pattern)
PATTERNS = [
    ("Alpaca key id", re.compile(r"\bPK[A-Z0-9]{16,}\b")),
    ("Anthropic key", re.compile(r"sk-ant-[A-Za-z0-9_\-]{20,}")),
    ("OpenAI key", re.compile(r"sk-[A-Za-z0-9]{32,}")),
    ("AWS access key", re.compile(r"\bAKIA[0-9A-Z]{16}\b")),
    ("Supabase secret", re.compile(r"sb_(?:secret|publishable)_[A-Za-z0-9_]{10,}")),
    ("Private key block", re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY-----")),
    ("Hardcoded credential",
     re.compile(r"""(?i)(?:api[_-]?key|secret|secret[_-]?key|password|passwd|token)\s*"""
                r"""[=:]\s*['"][^'"\n]{8,}['"]""")),
]

# Lowercase substrings that mark a match as a safe placeholder / non-secret.
ALLOW = ("os.environ", "getpass", "get_secret", "require_secret", "example",
         "your-", "change-me", "redact", "xxxx", "<", '""', "''", "placeholder",
         "${", "secrets.", "patterns", "allow")


def scan_text(text: str) -> list:
    """Return [(label, snippet)] of likely secrets in `text`."""
    hits = []
    for label, pat in PATTERNS:
        for m in pat.finditer(text):
            seg = m.group(0)
            low = seg.lower()
            if any(a in low for a in ALLOW):
                continue
            hits.append((label, seg[:48]))
    return hits


def _staged_files() -> list:
    out = subprocess.run(["git", "diff", "--cached", "--name-only",
                          "--diff-filter=ACM"], capture_output=True, text=True)
    return [f for f in out.stdout.splitlines() if f.strip()]


def scan_paths(paths) -> dict:
    findings = {}
    for path in paths:
        if path.replace("\\", "/").endswith("venture/security/scan.py"):
            continue   # don't flag our own pattern definitions
        try:
            with open(path, "r", encoding="utf-8", errors="ignore") as f:
                hits = scan_text(f.read())
        except (OSError, IsADirectoryError):
            continue
        if hits:
            findings[path] = hits
    return findings


def main(argv) -> int:
    paths = _staged_files() if "--staged" in argv else [a for a in argv if not a.startswith("--")]
    findings = scan_paths(paths)
    if findings:
        print("[BLOCKED] Potential secrets detected:")
        for path, hits in findings.items():
            for label, snippet in hits:
                print(f"  {path}: {label} -> {snippet}")
        print("Move secrets to env/.env/vault (see SECURITY.md). Commit blocked.")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
