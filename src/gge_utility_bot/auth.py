import base64

from cryptography.hazmat.primitives import hashes, hmac
from cryptography.hazmat.primitives.asymmetric.ed25519 import (
    Ed25519PrivateKey,
)


def init(private_key: str) -> None:
    Auth.CONTROL_PRIVATE_KEY = private_key


class Auth:
    CONTROL_PRIVATE_KEY: str

    @staticmethod
    def client_digest(message: bytes, secret: bytes) -> str:
        hmac_obj = hmac.HMAC(secret, hashes.SHA256())
        hmac_obj.update(message)
        digest = hmac_obj.finalize()
        hex_digest = base64.b16encode(digest).decode()
        return hex_digest

    @classmethod
    def control_digest(cls, message: bytes) -> str:
        key = Ed25519PrivateKey.from_private_bytes(
            base64.b16decode(cls.CONTROL_PRIVATE_KEY),
        )
        digest = key.sign(message)
        hex_digest = base64.b16encode(digest).decode()
        return hex_digest
