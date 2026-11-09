
from decimal import Decimal

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.database import Base
from app.models import SmartPayRule, PayoutRecord
import app.services.payout_reconciliation as reconciliation


@pytest.fixture
def reconciliation_env(tmp_path, monkeypatch):
    engine = create_engine(
        f"sqlite:///{tmp_path / 'reconciliation.db'}"
    )

    Base.metadata.create_all(bind=engine)
    SessionLocal = sessionmaker(bind=engine)

    with SessionLocal() as db:
        rule = SmartPayRule(
            recipient_name="Reconciliation Test",
            amount=10.00,
            currency="USD",
            description="Payment security test",
            condition="Complete work",
            status="PAYOUT_REFUNDED",
        )

        db.add(rule)
        db.flush()

        payout = PayoutRecord(
            rule_id=rule.id,
            sender_batch_id="test-batch-001",
            paypal_batch_id="paypal-batch-001",
            receiver_email="sandbox@example.com",
            amount=Decimal("10.00"),
            currency="USD",
            status="PAYOUT_REFUNDED",
        )

        db.add(payout)
        db.flush()

        rule_id = rule.id
        payout_id = payout.id
        db.commit()

    def fake_paypal_details(batch_id):
        assert batch_id == "paypal-batch-001"

        return {
            "batch_header": {
                "payout_batch_id": "paypal-batch-001",
                "batch_status": "SUCCESS",
                "sender_batch_header": {
                    "sender_batch_id": "test-batch-001",
                },
            },
            "items": [
                {
                    "payout_batch_id": "paypal-batch-001",
                    "transaction_status": "SUCCESS",
                    "payout_item": {
                        "sender_item_id": "test-batch-001",
                        "recipient_type": "EMAIL",
                        "receiver": "sandbox@example.com",
                        "amount": {
                            "value": "10.00",
                            "currency": "USD",
                        },
                    },
                }
            ],
        }

    monkeypatch.setattr(
        reconciliation,
        "get_payout_details",
        fake_paypal_details,
    )

    try:
        yield SessionLocal, rule_id, payout_id
    finally:
        engine.dispose()


def test_refunded_payment_cannot_become_paid_again(
    reconciliation_env,
):
    SessionLocal, rule_id, payout_id = reconciliation_env

    with SessionLocal() as db:
        payout = db.get(PayoutRecord, payout_id)

        with pytest.raises(
            ValueError,
            match="Cannot overwrite a recorded payment reversal",
        ):
            reconciliation.reconcile_payout(db, payout)

        db.rollback()

    with SessionLocal() as db:
        rule = db.get(SmartPayRule, rule_id)
        payout = db.get(PayoutRecord, payout_id)

        assert rule.status == "PAYOUT_REFUNDED"
        assert payout.status == "PAYOUT_REFUNDED"
