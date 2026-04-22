"""Password hashing, validation, and verification helpers."""

from __future__ import annotations

import hashlib
import hmac
import os


PBKDF2_ALGORITHM = "sha256"
PBKDF2_ITERATIONS = 600_000
SALT_BYTES = 16
MIN_PASSWORD_LENGTH = 10


def hash_password(password: str) -> str:
    """Hash a password using PBKDF2-HMAC."""
    salt = os.urandom(SALT_BYTES)
    derived_key = hashlib.pbkdf2_hmac(
        PBKDF2_ALGORITHM,
        password.encode("utf-8"),
        salt,
        PBKDF2_ITERATIONS,
    )
    return (
        f"pbkdf2_{PBKDF2_ALGORITHM}"
        f"${PBKDF2_ITERATIONS}"
        f"${salt.hex()}"
        f"${derived_key.hex()}"
    )


def verify_password(password: str, stored_hash: str) -> bool:
    """Check a password against a stored PBKDF2-HMAC hash."""
    try:
        method, iterations_text, salt_hex, hash_hex = stored_hash.split("$", maxsplit=3)
    except ValueError:
        return False

    if method != f"pbkdf2_{PBKDF2_ALGORITHM}":
        return False

    try:
        iterations = int(iterations_text)
        salt = bytes.fromhex(salt_hex)
        expected_hash = bytes.fromhex(hash_hex)
    except ValueError:
        return False

    calculated_hash = hashlib.pbkdf2_hmac(
        PBKDF2_ALGORITHM,
        password.encode("utf-8"),
        salt,
        iterations,
    )
    return hmac.compare_digest(calculated_hash, expected_hash)


def validate_password_strength(password: str) -> list[str]:
    """Return validation messages for a weak password."""
    errors: list[str] = []
    if len(password) < MIN_PASSWORD_LENGTH:
        errors.append(f"Password must be at least {MIN_PASSWORD_LENGTH} characters long.")
    if password.lower() == password:
        errors.append("Password must include at least one uppercase letter.")
    if password.upper() == password:
        errors.append("Password must include at least one lowercase letter.")
    if not any(character.isdigit() for character in password):
        errors.append("Password must include at least one number.")
    return errors
