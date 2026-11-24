from functools import lru_cache

import jwt

from app.core.config import get_settings


class InvalidToken(Exception):
    pass


@lru_cache
def _jwks_client(url: str) -> jwt.PyJWKClient:
    return jwt.PyJWKClient(url, cache_keys=True, lifespan=600)


def verify_access_token(token: str) -> dict:
    """Valida assinatura, expiração e audiência de um JWT emitido pelo Supabase Auth."""
    s = get_settings()
    try:
        header = jwt.get_unverified_header(token)
        alg = header.get("alg", "")
        if alg.startswith("HS"):
            if not s.supabase_jwt_secret:
                raise InvalidToken("HS256 não habilitado")
            key = s.supabase_jwt_secret
            algorithms = ["HS256"]
        else:
            key = _jwks_client(s.jwks_url).get_signing_key_from_jwt(token).key
            algorithms = ["ES256", "RS256"]
        return jwt.decode(
            token,
            key,
            algorithms=algorithms,
            audience=s.jwt_audience,
            options={"require": ["exp", "sub", "aud"]},
        )
    except InvalidToken:
        raise
    except Exception as exc:  # qualquer falha de parsing/assinatura vira token inválido
        raise InvalidToken(str(exc)) from exc
