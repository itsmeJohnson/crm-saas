"""AES-256-GCM encryption for at-rest secrets (telephony/provider credentials).

The key comes from the ``TELEPHONY_ENCRYPTION_KEY`` env var — a base64-encoded
32-byte key. Ciphertext is ``base64(nonce(12) || gcm_ciphertext_with_tag)`` so
each encryption is randomised and authenticated. Decrypted values are used only
server-side when calling a provider; they are never returned to any client.
"""
import base64
import os

from cryptography.hazmat.primitives.ciphers.aead import AESGCM

_NONCE_BYTES = 12


def _load_key() -> bytes:
    raw = os.getenv("TELEPHONY_ENCRYPTION_KEY")
    if not raw:
        raise RuntimeError(
            "TELEPHONY_ENCRYPTION_KEY is not set. Generate one with "
            "`python -c \"import os,base64;print(base64.b64encode(os.urandom(32)).decode())\"` "
            "and add it to the backend environment."
        )
    try:
        key = base64.b64decode(raw)
    except Exception as exc:  # noqa: BLE001
        raise RuntimeError("TELEPHONY_ENCRYPTION_KEY must be valid base64.") from exc
    if len(key) != 32:
        raise RuntimeError("TELEPHONY_ENCRYPTION_KEY must decode to 32 bytes (AES-256).")
    return key


def encrypt(plaintext: str | None) -> str | None:
    """Encrypt a UTF-8 string to base64(nonce||ciphertext). None/"" -> None."""
    if plaintext is None or plaintext == "":
        return None
    key = _load_key()
    nonce = os.urandom(_NONCE_BYTES)
    ct = AESGCM(key).encrypt(nonce, plaintext.encode("utf-8"), None)
    return base64.b64encode(nonce + ct).decode("ascii")


def decrypt(token: str | None) -> str | None:
    """Decrypt a value produced by :func:`encrypt`. None -> None. Raises on tamper."""
    if not token:
        return None
    key = _load_key()
    blob = base64.b64decode(token)
    nonce, ct = blob[:_NONCE_BYTES], blob[_NONCE_BYTES:]
    return AESGCM(key).decrypt(nonce, ct, None).decode("utf-8")
