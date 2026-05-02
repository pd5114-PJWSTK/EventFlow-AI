from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.models.ops import IdempotencyRecord, IdempotencyStatus


class IdempotencyConflictError(ValueError):
    pass


class IdempotencyPendingError(ValueError):
    pass


@dataclass(frozen=True)
class IdempotencyReservation:
    record: IdempotencyRecord | None
    replay_payload: dict[str, Any] | None
    replayed: bool


def reserve_idempotency(
    db: Session,
    *,
    scope: str,
    idempotency_key: str | None,
    event_id: str | None,
    request_payload: dict[str, Any],
) -> IdempotencyReservation:
    if not idempotency_key:
        return IdempotencyReservation(record=None, replay_payload=None, replayed=False)

    fingerprint = _payload_fingerprint(request_payload)
    existing = (
        db.query(IdempotencyRecord)
        .filter(
            IdempotencyRecord.scope == scope,
            IdempotencyRecord.idempotency_key == idempotency_key,
        )
        .first()
    )
    if existing is not None:
        return _evaluate_existing(existing, fingerprint)

    record = IdempotencyRecord(
        scope=scope,
        idempotency_key=idempotency_key,
        event_id=event_id,
        request_fingerprint=fingerprint,
        status=IdempotencyStatus.processing,
    )
    db.add(record)
    try:
        db.flush()
    except IntegrityError:
        db.rollback()
        existing = (
            db.query(IdempotencyRecord)
            .filter(
                IdempotencyRecord.scope == scope,
                IdempotencyRecord.idempotency_key == idempotency_key,
            )
            .first()
        )
        if existing is None:
            raise
        return _evaluate_existing(existing, fingerprint)

    return IdempotencyReservation(record=record, replay_payload=None, replayed=False)


def complete_idempotency(
    db: Session,
    *,
    record: IdempotencyRecord | None,
    response_payload: dict[str, Any],
) -> None:
    if record is None:
        return
    record.status = IdempotencyStatus.completed
    record.response_payload = response_payload
    record.error_code = None
    record.error_message = None
    record.updated_at = datetime.now(UTC)
    db.add(record)
    db.commit()


def fail_idempotency(
    db: Session,
    *,
    record: IdempotencyRecord | None,
    error_code: str,
    error_message: str,
) -> None:
    if record is None:
        return
    record.status = IdempotencyStatus.failed
    record.error_code = error_code
    record.error_message = error_message
    record.updated_at = datetime.now(UTC)
    db.add(record)
    db.commit()


def _evaluate_existing(
    record: IdempotencyRecord,
    fingerprint: str,
) -> IdempotencyReservation:
    if record.request_fingerprint != fingerprint:
        raise IdempotencyConflictError(
            "Idempotency key reused with a different payload."
        )
    if record.status == IdempotencyStatus.completed and record.response_payload is not None:
        return IdempotencyReservation(
            record=record,
            replay_payload=record.response_payload,
            replayed=True,
        )
    raise IdempotencyPendingError("Request with this idempotency key is still processing.")


def _payload_fingerprint(payload: dict[str, Any]) -> str:
    canonical = json.dumps(payload, sort_keys=True, separators=(",", ":"), default=str)
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()
