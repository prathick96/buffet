"""
venture/security/vault.py — hardened encrypted secrets vault.

Fixes the legacy SecureKeyStore weaknesses:
  - Master password comes from env (VENTURE_MASTER_PASSWORD) or is passed in —
    NEVER hardcoded.
  - Key derivation is **scrypt with a random per-vault salt** (not bare SHA-256),
    so the encryption key is expensive to brute-force.
  - The encrypted vault lives OUTSIDE the repo by default (~/.venture/vault.enc)
    and is chmod 600.

File format: [16-byte salt][Fernet token]. Same password + same salt -> same key.

License: original code (cryptography is BSD/Apache) -> commercial-clean.
"""
from __future__ import annotations

import base64
import json
import os
import secrets as _secrets
from hashlib import scrypt
from pathlib import Path

from cryptography.fernet import Fernet, InvalidToken

MASTER_ENV = "VENTURE_MASTER_PASSWORD"
PATH_ENV = "VENTURE_VAULT_PATH"
DEFAULT_PATH = Path.home() / ".venture" / "vault.enc"
_SALT_LEN = 16
_SCRYPT = dict(n=2 ** 14, r=8, p=1, dklen=32)   # ~tens of ms/derivation on CPU


class VaultLocked(Exception):
    """No/!wrong master password, or vault could not be decrypted."""


class Vault:
    def __init__(self, master_password: str | None = None, path=None):
        self._master = master_password or os.environ.get(MASTER_ENV)
        if not self._master:
            raise VaultLocked(
                f"No master password. Set ${MASTER_ENV} or pass master_password=.")
        self.path = Path(path or os.environ.get(PATH_ENV) or DEFAULT_PATH)
        self._data: dict = {}
        self._salt: bytes = b""
        self._load()

    def _derive(self, salt: bytes) -> Fernet:
        raw = scrypt(self._master.encode(), salt=salt, **_SCRYPT)
        return Fernet(base64.urlsafe_b64encode(raw))

    def _load(self) -> None:
        if not self.path.exists():
            self._salt = _secrets.token_bytes(_SALT_LEN)   # new vault
            self._data = {}
            return
        blob = self.path.read_bytes()
        self._salt, token = blob[:_SALT_LEN], blob[_SALT_LEN:]
        try:
            self._data = json.loads(self._derive(self._salt).decrypt(token).decode())
        except (InvalidToken, ValueError):
            raise VaultLocked("Wrong master password (vault decryption failed).")

    def _save(self) -> None:
        token = self._derive(self._salt).encrypt(json.dumps(self._data).encode())
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_bytes(self._salt + token)
        try:
            os.chmod(self.path, 0o600)
        except OSError:
            pass   # best-effort on platforms without POSIX perms

    # --- API -----------------------------------------------------------------
    def set(self, name: str, value: str) -> None:
        self._data[name] = value
        self._save()

    def get(self, name: str, default=None):
        return self._data.get(name, default)

    def require(self, name: str) -> str:
        if name not in self._data:
            raise KeyError(f"Secret '{name}' not in vault {self.path}")
        return self._data[name]

    def list(self) -> list:
        return sorted(self._data)

    def delete(self, name: str) -> None:
        if self._data.pop(name, None) is not None:
            self._save()

    def rotate(self, name: str, new_value: str) -> None:
        self.set(name, new_value)
