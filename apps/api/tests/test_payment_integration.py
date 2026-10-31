import uuid

import pytest
from httpx import ASGITransport, AsyncClient

# Reuse the guarded test database and application setup.
from test_contract_integration import app


@pytest.mark.asyncio
async def test_payment_evaluation_lifecycle():
    suffix = uuid.uuid4().hex

    transport = ASGITransport(app=app)

    async with (
        AsyncClient(
            transport=transport,
            base_url="http://localhost:3000",
            headers={"Origin": "http://localhost:3000"},
        ) as owner,
        AsyncClient(
            transport=transport,
            base_url="http://localhost:3000",
            headers={"Origin": "http://localhost:3000"},
        ) as outsider,
    ):
        for client, prefix in (
            (owner, "payment-owner"),
            (outsider, "payment-outsider"),
        ):
            response = await client.post(
                "/api/auth/register",
                json={
                    "email": f"{prefix}-{suffix}@example.com",
                    "password": "IntentraIntegrationTest2026!",
                },
            )
            assert response.status_code == 201, response.text

        response = await owner.post(
            "/api/contracts",
            json={
                "merchant_id": "paypal_merchant_demo",
                "maximum_amount": "150.00",
                "currency": "USD",
            },
        )
        assert response.status_code == 201, response.text

        contract_id = response.json()["id"]

        proposal = {
            "contract_id": contract_id,
            "merchant_id": "paypal_merchant_demo",
            "amount": "89.00",
            "currency": "USD",
        }

        # Draft contracts cannot authorize payments.
        response = await owner.post(
            "/api/payments/evaluate",
            json=proposal,
        )
        assert response.status_code == 200, response.text
        assert response.json()["decision"] == "BLOCK"

        # Approve the contract.
        response = await owner.post(
            f"/api/contracts/{contract_id}/approve",
            json={"expected_version": 1},
        )
        assert response.status_code == 200, response.text

        # Valid payment.
        response = await owner.post(
            "/api/payments/evaluate",
            json=proposal,
        )
        assert response.status_code == 200, response.text
        assert response.json()["decision"] == "ALLOW"
        assert response.json()["contract_version"] == 2

        # Merchant substitution.
        response = await owner.post(
            "/api/payments/evaluate",
            json={**proposal, "merchant_id": "attacker_merchant"},
        )
        assert response.status_code == 200, response.text
        assert response.json()["decision"] == "BLOCK"

        # Overspending.
        response = await owner.post(
            "/api/payments/evaluate",
            json={**proposal, "amount": "199.00"},
        )
        assert response.status_code == 200, response.text
        assert response.json()["decision"] == "BLOCK"

        # Currency mismatch.
        response = await owner.post(
            "/api/payments/evaluate",
            json={**proposal, "currency": "EUR"},
        )
        assert response.status_code == 200, response.text
        assert response.json()["decision"] == "BLOCK"

        # Another user cannot evaluate the owner's contract.
        response = await outsider.post(
            "/api/payments/evaluate",
            json=proposal,
        )
        assert response.status_code == 404, response.text

        # Revoke the contract.
        response = await owner.post(
            f"/api/contracts/{contract_id}/revoke",
            json={"expected_version": 2},
        )
        assert response.status_code == 200, response.text

        # Revoked contracts cannot authorize payments.
        response = await owner.post(
            "/api/payments/evaluate",
            json=proposal,
        )
        assert response.status_code == 200, response.text
        assert response.json()["decision"] == "BLOCK"
        assert response.json()["contract_version"] == 3


@pytest.mark.asyncio
async def test_payment_evaluations_are_persisted():
    from decimal import Decimal

    from sqlalchemy import select

    from intentra.database import SessionLocal
    from intentra.models.payment_evaluation import PaymentEvaluationRecord

    suffix = uuid.uuid4().hex

    transport = ASGITransport(app=app)

    async with AsyncClient(
        transport=transport,
        base_url="http://localhost:3000",
        headers={"Origin": "http://localhost:3000"},
    ) as client:
        response = await client.post(
            "/api/auth/register",
            json={
                "email": f"audit-{suffix}@example.com",
                "password": "IntentraIntegrationTest2026!",
            },
        )
        assert response.status_code == 201, response.text
        user_id = uuid.UUID(response.json()["id"])

        response = await client.post(
            "/api/contracts",
            json={
                "merchant_id": "paypal_audit_merchant",
                "maximum_amount": "150.00",
                "currency": "USD",
            },
        )
        assert response.status_code == 201, response.text
        contract_id = response.json()["id"]

        response = await client.post(
            f"/api/contracts/{contract_id}/approve",
            json={"expected_version": 1},
        )
        assert response.status_code == 200, response.text

        proposal = {
            "contract_id": contract_id,
            "merchant_id": "paypal_audit_merchant",
            "amount": "89.00",
            "currency": "USD",
        }

        allowed = await client.post(
            "/api/payments/evaluate",
            json=proposal,
        )
        assert allowed.status_code == 200, allowed.text
        assert allowed.json()["decision"] == "ALLOW"

        blocked = await client.post(
            "/api/payments/evaluate",
            json={
                **proposal,
                "merchant_id": "unauthorized_merchant",
            },
        )
        assert blocked.status_code == 200, blocked.text
        assert blocked.json()["decision"] == "BLOCK"

        allowed_id = uuid.UUID(allowed.json()["evaluation_id"])
        blocked_id = uuid.UUID(blocked.json()["evaluation_id"])

        assert allowed_id != blocked_id

    async with SessionLocal() as db:
        rows = (
            await db.scalars(
                select(PaymentEvaluationRecord).where(
                    PaymentEvaluationRecord.contract_id
                    == uuid.UUID(contract_id)
                )
            )
        ).all()

        assert len(rows) == 2

        by_id = {row.id: row for row in rows}

        assert set(by_id) == {allowed_id, blocked_id}

        allow_record = by_id[allowed_id]
        assert allow_record.actor_id == user_id
        assert allow_record.contract_version == 2
        assert allow_record.merchant_id == "paypal_audit_merchant"
        assert allow_record.amount == Decimal("89.00")
        assert allow_record.currency == "USD"
        assert allow_record.decision == "ALLOW"
        assert allow_record.created_at is not None

        block_record = by_id[blocked_id]
        assert block_record.actor_id == user_id
        assert block_record.contract_version == 2
        assert block_record.merchant_id == "unauthorized_merchant"
        assert block_record.amount == Decimal("89.00")
        assert block_record.currency == "USD"
        assert block_record.decision == "BLOCK"
        assert "Merchant" in block_record.reason
        assert block_record.created_at is not None


@pytest.mark.asyncio
async def test_payment_history_is_ordered_and_owner_isolated():
    suffix = uuid.uuid4().hex
    transport = ASGITransport(app=app)

    async with (
        AsyncClient(
            transport=transport,
            base_url="http://localhost:3000",
            headers={"Origin": "http://localhost:3000"},
        ) as owner,
        AsyncClient(
            transport=transport,
            base_url="http://localhost:3000",
            headers={"Origin": "http://localhost:3000"},
        ) as outsider,
    ):
        for client, prefix in (
            (owner, "history-owner"),
            (outsider, "history-outsider"),
        ):
            response = await client.post(
                "/api/auth/register",
                json={
                    "email": f"{prefix}-{suffix}@example.com",
                    "password": "IntentraIntegrationTest2026!",
                },
            )
            assert response.status_code == 201, response.text

        response = await owner.post(
            "/api/contracts",
            json={
                "merchant_id": "history_merchant",
                "maximum_amount": "100.00",
                "currency": "USD",
            },
        )
        assert response.status_code == 201, response.text
        contract_id = response.json()["id"]

        response = await owner.post(
            f"/api/contracts/{contract_id}/approve",
            json={"expected_version": 1},
        )
        assert response.status_code == 200, response.text

        proposal = {
            "contract_id": contract_id,
            "merchant_id": "history_merchant",
            "amount": "25.00",
            "currency": "USD",
        }

        first = await owner.post(
            "/api/payments/evaluate",
            json=proposal,
        )
        assert first.status_code == 200, first.text
        assert first.json()["decision"] == "ALLOW"

        second = await owner.post(
            "/api/payments/evaluate",
            json={**proposal, "amount": "150.00"},
        )
        assert second.status_code == 200, second.text
        assert second.json()["decision"] == "BLOCK"

        history = await owner.get(
            "/api/payments/evaluations",
            params={"contract_id": contract_id},
        )
        assert history.status_code == 200, history.text

        items = history.json()["items"]
        assert len(items) == 2

        returned_ids = {
            item["evaluation_id"] for item in items
        }
        assert returned_ids == {
            first.json()["evaluation_id"],
            second.json()["evaluation_id"],
        }

        for item in items:
            assert item["contract_id"] == contract_id
            assert item["contract_version"] == 2
            assert item["created_at"]
            assert item["reason"]

        timestamps = [
            (item["created_at"], item["evaluation_id"])
            for item in items
        ]
        assert timestamps == sorted(timestamps, reverse=True)

        # Another user must not see this contract's history.
        forbidden = await outsider.get(
            "/api/payments/evaluations",
            params={"contract_id": contract_id},
        )
        assert forbidden.status_code == 404, forbidden.text

        # Unauthenticated requests must be rejected.
        async with AsyncClient(
            transport=transport,
            base_url="http://localhost:3000",
        ) as anonymous:
            unauthenticated = await anonymous.get(
                "/api/payments/evaluations",
                params={"contract_id": contract_id},
            )
            assert unauthenticated.status_code == 401


@pytest.mark.asyncio
async def test_reservation_budget_and_idempotency():
    suffix = uuid.uuid4().hex
    transport = ASGITransport(app=app)

    async with AsyncClient(
        transport=transport,
        base_url="http://localhost:3000",
        headers={"Origin": "http://localhost:3000"},
    ) as client:
        response = await client.post(
            "/api/auth/register",
            json={
                "email": f"reservation-{suffix}@example.com",
                "password": "IntentraIntegrationTest2026!",
            },
        )
        assert response.status_code == 201, response.text

        response = await client.post(
            "/api/contracts",
            json={
                "merchant_id": "reservation_merchant",
                "maximum_amount": "100.00",
                "currency": "USD",
            },
        )
        assert response.status_code == 201, response.text
        contract_id = response.json()["id"]

        response = await client.post(
            f"/api/contracts/{contract_id}/approve",
            json={"expected_version": 1},
        )
        assert response.status_code == 200, response.text

        base = {
            "contract_id": contract_id,
            "merchant_id": "reservation_merchant",
            "currency": "USD",
        }

        async def reserve(key, amount):
            return await client.post(
                "/api/payments/reserve",
                json={
                    **base,
                    "idempotency_key": key,
                    "amount": amount,
                },
            )

        first = await reserve("payment-a", "60.00")
        assert first.status_code == 200, first.text
        assert first.json()["status"] == "RESERVED"
        assert first.json()["remaining_amount"] == "40.00"

        second = await reserve("payment-b", "30.00")
        assert second.status_code == 200, second.text
        assert second.json()["status"] == "RESERVED"
        assert second.json()["remaining_amount"] == "10.00"

        third = await reserve("payment-c", "20.00")
        assert third.status_code == 200, third.text
        assert third.json()["status"] == "BLOCKED"
        assert third.json()["remaining_amount"] == "10.00"

        # Retrying the same logical request must not reserve again.
        retry = await reserve("payment-a", "60.00")
        assert retry.status_code == 200, retry.text
        assert retry.json()["reservation_id"] == first.json()["reservation_id"]
        assert retry.json()["remaining_amount"] == "10.00"

        # Reusing a key with different payment details is forbidden.
        conflict = await reserve("payment-a", "5.00")
        assert conflict.status_code == 409, conflict.text

        # A blocked attempt must not consume the remaining budget.
        final = await reserve("payment-d", "10.00")
        assert final.status_code == 200, final.text
        assert final.json()["status"] == "RESERVED"
        assert final.json()["remaining_amount"] == "0.00"


@pytest.mark.asyncio
async def test_concurrent_reservations_cannot_exceed_budget():
    import asyncio
    from decimal import Decimal

    from sqlalchemy import func, select

    from intentra.database import SessionLocal
    from intentra.models.payment_reservation import PaymentReservationRecord

    suffix = uuid.uuid4().hex
    transport = ASGITransport(app=app)

    async with AsyncClient(
        transport=transport,
        base_url="http://localhost:3000",
        headers={"Origin": "http://localhost:3000"},
    ) as client:
        response = await client.post(
            "/api/auth/register",
            json={
                "email": f"concurrent-{suffix}@example.com",
                "password": "IntentraIntegrationTest2026!",
            },
        )
        assert response.status_code == 201, response.text

        response = await client.post(
            "/api/contracts",
            json={
                "merchant_id": "concurrent_merchant",
                "maximum_amount": "100.00",
                "currency": "USD",
            },
        )
        assert response.status_code == 201, response.text
        contract_id = response.json()["id"]

        response = await client.post(
            f"/api/contracts/{contract_id}/approve",
            json={"expected_version": 1},
        )
        assert response.status_code == 200, response.text

        async def reserve(index):
            return await client.post(
                "/api/payments/reserve",
                json={
                    "contract_id": contract_id,
                    "idempotency_key": f"concurrent-{index}",
                    "merchant_id": "concurrent_merchant",
                    "amount": "60.00",
                    "currency": "USD",
                },
            )

        responses = await asyncio.gather(
            *(reserve(index) for index in range(10))
        )

        assert all(
            response.status_code == 200
            for response in responses
        ), [(response.status_code, response.text) for response in responses]

        statuses = [
            response.json()["status"]
            for response in responses
        ]

        assert statuses.count("RESERVED") == 1
        assert statuses.count("BLOCKED") == 9

    async with SessionLocal() as db:
        total = await db.scalar(
            select(
                func.coalesce(
                    func.sum(PaymentReservationRecord.amount),
                    0,
                )
            ).where(
                PaymentReservationRecord.contract_id
                == uuid.UUID(contract_id),
                PaymentReservationRecord.status == "RESERVED",
            )
        )

        assert total == Decimal("60.00")


@pytest.mark.asyncio
async def test_reservations_respect_revocation_and_ownership():
    suffix = uuid.uuid4().hex
    transport = ASGITransport(app=app)

    async with (
        AsyncClient(
            transport=transport,
            base_url="http://localhost:3000",
            headers={"Origin": "http://localhost:3000"},
        ) as owner,
        AsyncClient(
            transport=transport,
            base_url="http://localhost:3000",
            headers={"Origin": "http://localhost:3000"},
        ) as outsider,
    ):
        for client, prefix in (
            (owner, "revoke-owner"),
            (outsider, "revoke-outsider"),
        ):
            response = await client.post(
                "/api/auth/register",
                json={
                    "email": f"{prefix}-{suffix}@example.com",
                    "password": "IntentraIntegrationTest2026!",
                },
            )
            assert response.status_code == 201, response.text

        response = await owner.post(
            "/api/contracts",
            json={
                "merchant_id": "revoke_merchant",
                "maximum_amount": "100.00",
                "currency": "USD",
            },
        )
        assert response.status_code == 201, response.text
        contract_id = response.json()["id"]

        base = {
            "contract_id": contract_id,
            "merchant_id": "revoke_merchant",
            "amount": "40.00",
            "currency": "USD",
        }

        # A draft contract must not allocate budget.
        draft = await owner.post(
            "/api/payments/reserve",
            json={**base, "idempotency_key": "draft-attempt"},
        )
        assert draft.status_code == 200, draft.text
        assert draft.json()["status"] == "BLOCKED"

        response = await owner.post(
            f"/api/contracts/{contract_id}/approve",
            json={"expected_version": 1},
        )
        assert response.status_code == 200, response.text

        # An outsider cannot reserve against this contract.
        outsider_response = await outsider.post(
            "/api/payments/reserve",
            json={**base, "idempotency_key": "outsider-attempt"},
        )
        assert outsider_response.status_code == 404

        reserved = await owner.post(
            "/api/payments/reserve",
            json={**base, "idempotency_key": "approved-payment"},
        )
        assert reserved.status_code == 200, reserved.text
        assert reserved.json()["status"] == "RESERVED"
        assert reserved.json()["remaining_amount"] == "60.00"

        response = await owner.post(
            f"/api/contracts/{contract_id}/revoke",
            json={"expected_version": 2},
        )
        assert response.status_code == 200, response.text

        # New reservations must be blocked after revocation.
        revoked = await owner.post(
            "/api/payments/reserve",
            json={**base, "idempotency_key": "after-revocation"},
        )
        assert revoked.status_code == 200, revoked.text
        assert revoked.json()["status"] == "BLOCKED"
        assert revoked.json()["remaining_amount"] == "60.00"
        assert revoked.json()["contract_version"] == 3

        # Replaying an existing reservation must not allocate more budget.
        replay = await owner.post(
            "/api/payments/reserve",
            json={**base, "idempotency_key": "approved-payment"},
        )
        assert replay.status_code == 200, replay.text
        assert replay.json()["reservation_id"] == reserved.json()["reservation_id"]
        assert replay.json()["remaining_amount"] == "60.00"


@pytest.mark.asyncio
async def test_concurrent_revocation_and_reservation():
    import asyncio
    from decimal import Decimal

    from sqlalchemy import func, select

    from intentra.database import SessionLocal
    from intentra.models.payment_reservation import PaymentReservationRecord

    suffix = uuid.uuid4().hex
    transport = ASGITransport(app=app)

    async with AsyncClient(
        transport=transport,
        base_url="http://localhost:3000",
        headers={"Origin": "http://localhost:3000"},
    ) as client:
        response = await client.post(
            "/api/auth/register",
            json={
                "email": f"race-{suffix}@example.com",
                "password": "IntentraIntegrationTest2026!",
            },
        )
        assert response.status_code == 201, response.text

        response = await client.post(
            "/api/contracts",
            json={
                "merchant_id": "race_merchant",
                "maximum_amount": "100.00",
                "currency": "USD",
            },
        )
        assert response.status_code == 201, response.text
        contract_id = response.json()["id"]

        response = await client.post(
            f"/api/contracts/{contract_id}/approve",
            json={"expected_version": 1},
        )
        assert response.status_code == 200, response.text

        async def revoke():
            return await client.post(
                f"/api/contracts/{contract_id}/revoke",
                json={"expected_version": 2},
            )

        async def reserve():
            return await client.post(
                "/api/payments/reserve",
                json={
                    "contract_id": contract_id,
                    "idempotency_key": "race-payment",
                    "merchant_id": "race_merchant",
                    "amount": "60.00",
                    "currency": "USD",
                },
            )

        revoke_response, reserve_response = await asyncio.gather(
            revoke(),
            reserve(),
        )

        assert revoke_response.status_code == 200, revoke_response.text
        assert reserve_response.status_code == 200, reserve_response.text

        assert revoke_response.json()["status"] == "REVOKED"

        reservation_status = reserve_response.json()["status"]
        assert reservation_status in {"RESERVED", "BLOCKED"}

        # Once revocation has committed, no new reservation may succeed.
        later = await client.post(
            "/api/payments/reserve",
            json={
                "contract_id": contract_id,
                "idempotency_key": "after-race",
                "merchant_id": "race_merchant",
                "amount": "10.00",
                "currency": "USD",
            },
        )

        assert later.status_code == 200, later.text
        assert later.json()["status"] == "BLOCKED"

    async with SessionLocal() as db:
        total = await db.scalar(
            select(
                func.coalesce(
                    func.sum(PaymentReservationRecord.amount),
                    0,
                )
            ).where(
                PaymentReservationRecord.contract_id
                == uuid.UUID(contract_id),
                PaymentReservationRecord.status == "RESERVED",
            )
        )

        assert total in {Decimal("0.00"), Decimal("60.00")}

        if reservation_status == "BLOCKED":
            assert total == Decimal("0.00")
        else:
            assert total == Decimal("60.00")
