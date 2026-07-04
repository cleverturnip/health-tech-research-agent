"""Password hashing for the simple-password login (P1.4).

Dependency-free PBKDF2-SHA256 with a per-hash random salt, encoded as
`pbkdf2_sha256$<iterations>$<b64 salt>$<b64 hash>`. The plaintext password is NEVER stored — only this hash,
which lives in the `HTRA_PASSWORD_HASH` secret (never in the repo). Verification is constant-time.
"""

from __future__ import annotations

import base64
import hashlib
import hmac
import os

_ALGO = "pbkdf2_sha256"
_ITERATIONS = 240_000
_SALT_BYTES = 16


def hash_password(password: str, *, iterations: int = _ITERATIONS, salt: bytes | None = None) -> str:
    """Hash a plaintext password into the encoded `pbkdf2_sha256$iters$salt$hash` string."""
    if salt is None:
        salt = os.urandom(_SALT_BYTES)
    dk = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, iterations)
    return f"{_ALGO}${iterations}${base64.b64encode(salt).decode()}${base64.b64encode(dk).decode()}"


def verify_password(password: str, encoded: str) -> bool:
    """Constant-time check of a plaintext password against an encoded hash. A malformed hash -> False."""
    try:
        algo, iterations_s, salt_b64, hash_b64 = encoded.split("$")
        if algo != _ALGO:
            return False
        iterations = int(iterations_s)
        salt = base64.b64decode(salt_b64)
        expected = base64.b64decode(hash_b64)
    except (ValueError, TypeError):
        return False
    dk = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, iterations)
    return hmac.compare_digest(dk, expected)
