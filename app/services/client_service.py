from __future__ import annotations

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models.core import Client
from app.schemas.clients import ClientCreate, ClientUpdate


def create_client(db: Session, payload: ClientCreate) -> Client:
    client = Client(**payload.model_dump())
    db.add(client)
    db.commit()
    db.refresh(client)
    return client


def get_client(db: Session, client_id: str) -> Client | None:
    return db.get(Client, client_id)


def list_clients(db: Session, limit: int, offset: int) -> tuple[list[Client], int]:
    items = (
        db.execute(
            select(Client)
            .order_by(Client.created_at.desc())
            .offset(offset)
            .limit(limit)
        )
        .scalars()
        .all()
    )
    total = db.scalar(select(func.count()).select_from(Client)) or 0
    return items, int(total)


def update_client(db: Session, client: Client, payload: ClientUpdate) -> Client:
    for key, value in payload.model_dump(exclude_unset=True).items():
        setattr(client, key, value)
    db.add(client)
    db.commit()
    db.refresh(client)
    return client


def delete_client(db: Session, client: Client) -> None:
    db.delete(client)
    db.commit()
