"""Cadastros de apoio: categorias, pessoas (contatos sem login) e configurações."""

import uuid
from datetime import UTC, datetime

from fastapi import APIRouter, status
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

from app.api.v1.deps import DB, RequestId
from app.core.errors import Conflict, NotFound
from app.domains.support import audit, snapshot
from app.models import AppSettings, Category, Person
from app.schemas.finance import (
    CategoryCreate,
    CategoryOut,
    PersonCreate,
    PersonOut,
    PersonUpdate,
    SettingsOut,
    SettingsUpdate,
)

router = APIRouter()


@router.get("/categories", response_model=list[CategoryOut], tags=["Categorias"])
def list_categories(db: DB, include_archived: bool = False):
    q = select(Category).order_by(Category.kind, Category.name)
    if not include_archived:
        q = q.where(Category.archived_at.is_(None))
    return db.scalars(q).all()


@router.post("/categories", response_model=CategoryOut, status_code=status.HTTP_201_CREATED, tags=["Categorias"])
def create_category(data: CategoryCreate, db: DB, rid: RequestId):
    if data.parent_id:
        parent = db.get(Category, data.parent_id)
        if parent is None:
            raise NotFound("Categoria pai")
        if parent.kind != data.kind:
            raise Conflict("category_kind_mismatch", "Subcategoria deve ter o mesmo tipo da categoria pai.")
    cat = Category(**data.model_dump())
    db.add(cat)
    try:
        db.flush()
    except IntegrityError:
        db.rollback()
        raise Conflict("category_exists", "Já existe uma categoria com esse nome.") from None
    audit(db, "category", cat.id, "create", None, data.model_dump(), rid)
    db.commit()
    return cat


@router.get("/people", response_model=list[PersonOut], tags=["Pessoas"])
def list_people(db: DB, include_archived: bool = False):
    q = select(Person).order_by(Person.display_name)
    if not include_archived:
        q = q.where(Person.archived_at.is_(None))
    return db.scalars(q).all()


@router.post("/people", response_model=PersonOut, status_code=status.HTTP_201_CREATED, tags=["Pessoas"])
def create_person(data: PersonCreate, db: DB, rid: RequestId):
    person = Person(**data.model_dump())
    db.add(person)
    db.flush()
    audit(db, "person", person.id, "create", None, data.model_dump(), rid)
    db.commit()
    return person


@router.patch("/people/{person_id}", response_model=PersonOut, tags=["Pessoas"])
def update_person(person_id: uuid.UUID, data: PersonUpdate, db: DB, rid: RequestId):
    person = db.get(Person, person_id)
    if person is None:
        raise NotFound("Pessoa")
    fields = ("display_name", "contact", "notes", "archived_at")
    before = snapshot(person, fields)
    changes = data.model_dump(exclude_unset=True)
    archived = changes.pop("archived", None)
    for k, v in changes.items():
        setattr(person, k, v)
    if archived is not None:
        person.archived_at = datetime.now(UTC) if archived else None
    audit(db, "person", person.id, "update", before, snapshot(person, fields), rid)
    db.commit()
    return person


def _settings(db) -> AppSettings:
    s = db.get(AppSettings, 1)
    if s is None:
        s = AppSettings(id=1)
        db.add(s)
        db.flush()
    return s


@router.get("/settings", response_model=SettingsOut, tags=["Configurações"])
def get_settings_(db: DB):
    s = _settings(db)
    db.commit()
    return s


@router.patch("/settings", response_model=SettingsOut, tags=["Configurações"])
def update_settings(data: SettingsUpdate, db: DB):
    s = _settings(db)
    for k, v in data.model_dump(exclude_unset=True).items():
        setattr(s, k, v)
    db.commit()
    return s
