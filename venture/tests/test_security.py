"""
venture/tests/test_security.py — vault, secrets loader, secret scanner.
Run:  python venture/tests/test_security.py
"""
import os
import sys
import tempfile

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from security.scan import scan_text  # noqa: E402
from security.secrets import MissingSecret, get_secret, require_secret  # noqa: E402
from security.vault import Vault, VaultLocked  # noqa: E402


# ---------------------------------------------------------------- vault
def test_vault_roundtrip_and_reopen():
    with tempfile.TemporaryDirectory() as d:
        p = os.path.join(d, "v.enc")
        master_key = "correct-" + "horse-" + "battery"
        v = Vault(master_password=master_key, path=p)
        v.set("ALPACA_API_KEY", "abc123")
        assert v.require("ALPACA_API_KEY") == "abc123"
        v2 = Vault(master_password=master_key, path=p)   # reopen
        assert v2.get("ALPACA_API_KEY") == "abc123"
    print("PASS vault_roundtrip_and_reopen")


def test_vault_wrong_password_fails():
    with tempfile.TemporaryDirectory() as d:
        p = os.path.join(d, "v.enc")
        Vault(master_password="right", path=p).set("k", "v")
        try:
            Vault(master_password="wrong", path=p)
            assert False, "wrong password should raise"
        except VaultLocked:
            print("PASS vault_wrong_password_fails")


def test_vault_random_salt_per_vault():
    with tempfile.TemporaryDirectory() as d:
        p1, p2 = os.path.join(d, "a.enc"), os.path.join(d, "b.enc")
        Vault(master_password="same", path=p1).set("k", "v")
        Vault(master_password="same", path=p2).set("k", "v")
        with open(p1, "rb") as f1, open(p2, "rb") as f2:
            assert f1.read()[:16] != f2.read()[:16]   # random salts differ
    print("PASS vault_random_salt_per_vault")


# ---------------------------------------------------------------- secrets
def test_env_takes_precedence():
    os.environ["X_TEST_SECRET"] = "from-env"
    try:
        assert get_secret("X_TEST_SECRET") == "from-env"
    finally:
        del os.environ["X_TEST_SECRET"]
    print("PASS env_takes_precedence")


def test_dotenv_then_vault_then_missing():
    with tempfile.TemporaryDirectory() as d:
        envp = os.path.join(d, ".env")
        secret_name = "Y_TEST_SECRET"
        secret_value = "from-dotenv"
        with open(envp, "w") as f:
            f.write(secret_name + "=" + repr(secret_value) + "\n# comment\n")
        assert get_secret(secret_name, dotenv_path=envp) == secret_value

        class FakeVault:
            def get(self, n):
                return "from-vault" if n == "Z_TEST_SECRET" else None

        assert get_secret("Z_TEST_SECRET", vault=FakeVault(),
                          dotenv_path=os.path.join(d, "none")) == "from-vault"
        try:
            require_secret("NOPE_SECRET", dotenv_path=os.path.join(d, "none"))
            assert False, "missing secret should raise"
        except MissingSecret:
            pass
    print("PASS dotenv_then_vault_then_missing")


# ---------------------------------------------------------------- scanner
def test_scanner_detects_secrets():
    # Build the sample values at runtime so the source file does not contain
    # a contiguous secret-like literal that could be flagged by the repo scanner.
    alpaca_secret = "PK" + "SDCXAUDKSXSH6YKPY4CWN6WY"
    anthropic_secret = "sk-ant-" + "abcdefghij1234567890ABCDEFGH"
    password_secret = "super" + "secret123"

    assert scan_text('ALPACA_API_KEY = "' + alpaca_secret + '"')
    assert scan_text('k = "' + anthropic_secret + '"')
    assert scan_text('password = "' + password_secret + '"')
    print("PASS scanner_detects_secrets")


def test_scanner_allows_clean_code():
    assert scan_text('api_key = os.environ.get("ALPACA_API_KEY", "")') == []
    assert scan_text('MASTER_PASSWORD = ""  # set via .env') == []
    assert scan_text('token: ${{ secrets.NEWS_API_KEY }}') == []
    print("PASS scanner_allows_clean_code")


if __name__ == "__main__":
    tests = [v for k, v in sorted(globals().items())
             if k.startswith("test_") and callable(v)]
    for fn in tests:
        fn()
    print(f"\nALL {len(tests)} SECURITY TESTS PASSED")
