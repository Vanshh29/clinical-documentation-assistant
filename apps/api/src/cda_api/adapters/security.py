import hashlib
import hmac
import secrets
import time
import uuid

import jwt

from cda_api.config import Settings
from cda_api.domain.enums import Role
from cda_api.domain.errors import AuthenticationFailed
from cda_api.domain.principal import Principal

_SCRYPT_N, _SCRYPT_R, _SCRYPT_P = 2**14, 8, 1


def hash_password(password: str) -> str:
    salt = secrets.token_bytes(16)
    digest = hashlib.scrypt(
        password.encode(), salt=salt, n=_SCRYPT_N, r=_SCRYPT_R, p=_SCRYPT_P, dklen=32
    )
    return f"scrypt${salt.hex()}${digest.hex()}"


def verify_password(password: str, stored: str) -> bool:
    try:
        scheme, salt_hex, digest_hex = stored.split("$")
        if scheme != "scrypt":
            return False
        digest = hashlib.scrypt(
            password.encode(),
            salt=bytes.fromhex(salt_hex),
            n=_SCRYPT_N,
            r=_SCRYPT_R,
            p=_SCRYPT_P,
            dklen=32,
        )
    except ValueError:
        return False
    return hmac.compare_digest(digest.hex(), digest_hex)


class TokenService:
    """Issues and verifies OIDC-style JWTs. Swap `verify` for a JWKS-backed one in production."""

    def __init__(self, settings: Settings) -> None:
        self._s = settings

    def issue(self, principal: Principal) -> tuple[str, int]:
        now = int(time.time())
        ttl = self._s.auth_access_token_ttl_minutes * 60
        claims = {
            "iss": self._s.auth_jwt_issuer,
            "aud": self._s.auth_jwt_audience,
            "sub": str(principal.user_id),
            "email": principal.email,
            "role": principal.role.value,
            "iat": now,
            "exp": now + ttl,
            "jti": uuid.uuid4().hex,
        }
        return jwt.encode(claims, self._s.auth_jwt_secret, algorithm="HS256"), ttl

    def verify(self, token: str) -> Principal:
        try:
            claims = jwt.decode(
                token,
                self._s.auth_jwt_secret,
                algorithms=["HS256"],
                audience=self._s.auth_jwt_audience,
                issuer=self._s.auth_jwt_issuer,
                options={"require": ["exp", "iat", "sub", "role"]},
            )
            return Principal(
                user_id=uuid.UUID(claims["sub"]),
                role=Role(claims["role"]),
                email=claims.get("email", ""),
            )
        except (jwt.PyJWTError, ValueError) as exc:
            raise AuthenticationFailed("invalid or expired token") from exc
