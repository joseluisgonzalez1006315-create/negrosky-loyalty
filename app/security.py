import base64
import hashlib
import hmac
import json
import os
import secrets
import time

# La sesión del cliente se conserva durante años para no volver a pedir identificación.
TOKEN_TTL_SECONDS = 10 * 365 * 24 * 60 * 60


def _b64encode(value: bytes) -> str:
    return base64.urlsafe_b64encode(value).decode().rstrip("=")


def _b64decode(value: str) -> bytes:
    return base64.urlsafe_b64decode(value + "=" * (-len(value) % 4))


def hash_password(password: str) -> str:
    salt = secrets.token_bytes(16)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode(), salt, 310_000)
    return f"pbkdf2_sha256$310000${_b64encode(salt)}${_b64encode(digest)}"


def verify_password(password: str, encoded: str) -> bool:
    try:
        algorithm, rounds, salt, expected = encoded.split("$")
        if algorithm != "pbkdf2_sha256":
            return False
        digest = hashlib.pbkdf2_hmac(
            "sha256", password.encode(), _b64decode(salt), int(rounds)
        )
        return hmac.compare_digest(_b64encode(digest), expected)
    except (ValueError, TypeError):
        return False


def _secret() -> bytes:
    return os.getenv("NEGROSKY_SECRET", "local-development-secret-change-me").encode()


def create_token(user: dict, session_id: str) -> str:
    payload = {
        "type": "user",
        "sub": user["id"],
        "role": user["role"],
        "tenant_id": user["tenant_id"],
        "branch_id": user["branch_id"],
        "sid": session_id,
        "exp": int(time.time()) + TOKEN_TTL_SECONDS,
    }
    body = _b64encode(json.dumps(payload, separators=(",", ":")).encode())
    signature = _b64encode(hmac.new(_secret(), body.encode(), hashlib.sha256).digest())
    return f"{body}.{signature}"


def create_customer_token(customer: dict) -> str:
    payload = {
        "type": "customer",
        "sub": customer["id"],
        "tenant_id": customer["tenant_id"],
        "exp": int(time.time()) + TOKEN_TTL_SECONDS,
    }
    body = _b64encode(json.dumps(payload, separators=(",", ":")).encode())
    signature = _b64encode(hmac.new(_secret(), body.encode(), hashlib.sha256).digest())
    return f"{body}.{signature}"


def decode_token(token: str) -> dict:
    body, signature = token.split(".", 1)
    expected = _b64encode(hmac.new(_secret(), body.encode(), hashlib.sha256).digest())
    if not hmac.compare_digest(signature, expected):
        raise ValueError("Firma inválida")
    payload = json.loads(_b64decode(body))
    if payload["exp"] < int(time.time()):
        raise ValueError("Token expirado")
    return payload
