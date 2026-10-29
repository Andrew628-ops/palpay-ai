import json

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.database import Base
from app.models import PayPalWebhookEvent
from app.services import webhook_processing


def test_unsupported_webhook_is_ignored(tmp_path, monkeypatch):
    # Create an isolated test database.
    database_path = tmp_path / "webhook_test.db"

    engine = create_engine(
        f"sqlite:///{database_path}"
    )

    Base.metadata.create_all(bind=engine)

    TestingSessionLocal = sessionmaker(bind=engine)

    monkeypatch.setattr(
        webhook_processing,
        "SessionLocal",
        TestingSessionLocal
    )

    event_id = "WH-test-unsupported-1"

    # Simulate a previously verified and stored batch event.
    with TestingSessionLocal() as db:
        db.add(
            PayPalWebhookEvent(
                event_id=event_id,
                event_type="PAYMENT.PAYOUTSBATCH.SUCCESS",
                payload_json=json.dumps({
                    "id": event_id,
                    "event_type": "PAYMENT.PAYOUTSBATCH.SUCCESS"
                }),
                status="RECEIVED"
            )
        )
        db.commit()

    # Process the unsupported event.
    result = webhook_processing.process_saved_webhook(
        event_id
    )

    assert result == "IGNORED"

    # Verify that the database was updated.
    with TestingSessionLocal() as db:
        saved_event = db.get(
            PayPalWebhookEvent,
            event_id
        )

        assert saved_event.status == "IGNORED"

    # Duplicate processing must be safe.
    second_result = webhook_processing.process_saved_webhook(
        event_id
    )

    assert second_result == "IGNORED"

    engine.dispose()