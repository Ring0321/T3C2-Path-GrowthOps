"""Minimal append-only audit chain for reproducible research decisions."""

from __future__ import annotations

import hashlib
import json
from datetime import datetime
from threading import Lock
from typing import Any

from pydantic import AwareDatetime, Field

from t3c2_path.domain import FrozenModel


ZERO_HASH = "sha256:" + "0" * 64


def canonical_hash(payload: Any) -> str:
    encoded = json.dumps(
        payload,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
        default=str,
    ).encode("utf-8")
    return "sha256:" + hashlib.sha256(encoded).hexdigest()


class AuditEvent(FrozenModel):
    sequence: int = Field(ge=1)
    decision_id: str = Field(min_length=1)
    previous_hash: str = Field(pattern=r"^sha256:[0-9a-f]{64}$")
    payload_hash: str = Field(pattern=r"^sha256:[0-9a-f]{64}$")
    chain_hash: str = Field(pattern=r"^sha256:[0-9a-f]{64}$")
    created_at: AwareDatetime


def _chain_hash(
    sequence: int,
    decision_id: str,
    previous_hash: str,
    payload_hash: str,
    created_at: datetime,
) -> str:
    return canonical_hash(
        {
            "sequence": sequence,
            "decision_id": decision_id,
            "previous_hash": previous_hash,
            "payload_hash": payload_hash,
            "created_at": created_at.isoformat(),
        }
    )


class AppendOnlyAuditStore:
    """Thread-safe in-memory reference store.

    Production deployments must replace this with durable, access-controlled
    storage.  Only hashes are kept here; the raw payload remains in the caller's
    purpose-bound storage.
    """

    def __init__(self) -> None:
        self._events: list[AuditEvent] = []
        self._lock = Lock()

    def append(
        self, decision_id: str, payload: Any, *, created_at: datetime
    ) -> AuditEvent:
        if created_at.tzinfo is None:
            raise ValueError("created_at must be timezone-aware")
        payload_hash = canonical_hash(payload)
        with self._lock:
            sequence = len(self._events) + 1
            previous_hash = self._events[-1].chain_hash if self._events else ZERO_HASH
            event = AuditEvent(
                sequence=sequence,
                decision_id=decision_id,
                previous_hash=previous_hash,
                payload_hash=payload_hash,
                chain_hash=_chain_hash(
                    sequence, decision_id, previous_hash, payload_hash, created_at
                ),
                created_at=created_at,
            )
            self._events.append(event)
            return event

    def events(self) -> tuple[AuditEvent, ...]:
        with self._lock:
            return tuple(self._events)

    @staticmethod
    def verify(events: tuple[AuditEvent, ...]) -> bool:
        previous_hash = ZERO_HASH
        for expected_sequence, event in enumerate(events, start=1):
            if event.sequence != expected_sequence or event.previous_hash != previous_hash:
                return False
            expected_hash = _chain_hash(
                event.sequence,
                event.decision_id,
                event.previous_hash,
                event.payload_hash,
                event.created_at,
            )
            if event.chain_hash != expected_hash:
                return False
            previous_hash = event.chain_hash
        return True


__all__ = ["AppendOnlyAuditStore", "AuditEvent", "canonical_hash"]
