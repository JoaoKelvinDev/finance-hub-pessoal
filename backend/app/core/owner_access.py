import hmac
import logging

from fastapi import HTTPException, Request, status

from app.core.config import get_settings
from app.core.security import InvalidToken, verify_access_token

log = logging.getLogger("finance_hub.access")

_UNAUTHORIZED = HTTPException(
    status_code=status.HTTP_401_UNAUTHORIZED,
    detail="Sessão inválida ou expirada.",
    headers={"WWW-Authenticate": "Bearer"},
)


def require_owner(request: Request) -> str:
    """Aceita apenas a única identidade autorizada (OWNER_SUBJECT). Não há outros usuários."""
    owner = get_settings().owner_subject
    if not owner:
        raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE, "OWNER_SUBJECT não configurado.")

    auth = request.headers.get("authorization", "")
    scheme, _, token = auth.partition(" ")
    if scheme.lower() != "bearer" or not token:
        raise _UNAUTHORIZED
    try:
        claims = verify_access_token(token)
    except InvalidToken:
        raise _UNAUTHORIZED from None

    if not hmac.compare_digest(str(claims.get("sub", "")), owner):
        log.warning("acesso negado: identidade diferente da proprietária")
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Acesso restrito ao proprietário.")
    return owner
