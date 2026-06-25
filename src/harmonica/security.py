"""Lightweight passphrase hashing for device configs.

This is a LAN convenience lock so a returning device can re-claim its config by
passphrase, not strong internet-facing auth. Keep the daemon on a trusted network.
"""

from __future__ import annotations

import hashlib
import hmac
import os

_ITERATIONS = 120_000


def hash_passphrase(passphrase: str) -> str:
    salt = os.urandom(16)
    digest = hashlib.pbkdf2_hmac("sha256", passphrase.encode("utf-8"), salt, _ITERATIONS)
    return f"pbkdf2_sha256${_ITERATIONS}${salt.hex()}${digest.hex()}"


def verify_passphrase(passphrase: str, stored: str) -> bool:
    try:
        algorithm, iterations, salt_hex, digest_hex = stored.split("$")
    except ValueError:
        return False
    if algorithm != "pbkdf2_sha256":
        return False
    expected = bytes.fromhex(digest_hex)
    actual = hashlib.pbkdf2_hmac(
        "sha256", passphrase.encode("utf-8"), bytes.fromhex(salt_hex), int(iterations)
    )
    return hmac.compare_digest(expected, actual)
