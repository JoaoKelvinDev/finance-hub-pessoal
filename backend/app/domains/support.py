import hashlib
import json
import uuid
from collections.abc import Callable
from datetime import date, datetime
from zoneinfo import ZoneInfo

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.errors import Conflict
from app.models import AuditEvent, IdempotencyRecord


def now_local() -> datetime:
    return datetime.now(ZoneInfo(get_settings().app_timezone))


def today_local() -> date:
    return now_local().date()


def _default(o):
    if isinstance(o, (uuid.UUID, date, datetime)):
        return str(o)
    raise TypeError(type(o))


def payload_hash(payload: dict) -> str:
    raw = json.dumps(payload, sort_keys=True, default=_default, separators=(",", ":"))
    return hashlib.sha256(raw.encode()).hexdigest()


def run_idempotent(
    db: Session, key: str | None, operation: str, payload: dict, create: Callable[[], uuid.UUID]
) -> tuple[uuid.UUID, bool]:
    """Executa `create` uma única vez por chave. Retorna (id, criado_agora). Não faz commit."""
    if not key:
        return create(), True

    digest = payload_hash(payload)

    def _existing() -> tuple[uuid.UUID, bool] | None:
        rec = db.get(IdempotencyRecord, key)
        if rec is None:
            return None
        if rec.operation != operation or rec.payload_hash != digest:
            raise Conflict("idempotency_conflict", "Chave de idempotência já usada com outro conteúdo.")
        return rec.result_id, False

    found = _existing()
    if found:
        return found

    savepoint = db.begin_nested()
    try:
        result_id = create()
        db.add(IdempotencyRecord(key=key, operation=operation, payload_hash=digest, result_id=result_id))
        db.flush()
        savepoint.commit()
        return result_id, True
    except IntegrityError:
        savepoint.rollback()
        found = _existing()
        if found:
            return found
        raise


def audit(
    db: Session,
    entity_type: str,
    entity_id: uuid.UUID,
    operation: str,
    before: dict | None,
    after: dict | None,
    request_id: str | None,
) -> None:
    db.add(
        AuditEvent(
            entity_type=entity_type,
            entity_id=entity_id,
            operation=operation,
            before_json=json.loads(json.dumps(before, default=_default)) if before else None,
            after_json=json.loads(json.dumps(after, default=_default)) if after else None,
            request_id=request_id,
        )
    )


def snapshot(obj, fields: tuple[str, ...]) -> dict:
    return {f: getattr(obj, f) for f in fields}
