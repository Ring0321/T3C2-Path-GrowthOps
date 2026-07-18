from datetime import UTC, datetime

from t3c2_path.audit import AppendOnlyAuditStore, AuditEvent


NOW = datetime(2026, 7, 19, 8, 0, tzinfo=UTC)


def test_audit_hash_chain_verifies_and_detects_tampering() -> None:
    store = AppendOnlyAuditStore()
    store.append("decision-1", {"action": "PUBLISH"}, created_at=NOW)
    store.append("decision-2", {"action": "DEFER"}, created_at=NOW)
    events = store.events()
    assert AppendOnlyAuditStore.verify(events)

    tampered = (
        events[0],
        AuditEvent(
            **{
                **events[1].model_dump(),
                "payload_hash": "sha256:" + "0" * 64,
            }
        ),
    )
    assert not AppendOnlyAuditStore.verify(tampered)


def test_audit_payload_is_hashed_not_stored_as_raw_student_data() -> None:
    store = AppendOnlyAuditStore()
    event = store.append(
        "decision-1",
        {"subject_id": "synthetic-student-001", "action": "PUBLISH"},
        created_at=NOW,
    )
    dump = event.model_dump_json()
    assert "synthetic-student-001" not in dump
    assert event.payload_hash.startswith("sha256:")
