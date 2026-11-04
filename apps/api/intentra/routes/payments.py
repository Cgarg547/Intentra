import uuid
import os
import logging
from urllib.parse import urlsplit

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from intentra.database import get_db
from intentra.models.intent_contract import (
    IntentContractRecord,
    UserRecord,
)
from intentra.models.payment_evaluation import PaymentEvaluationRecord
from intentra.models.payment_attempt import PaymentAttemptRecord
from intentra.models.payment_attempt_event import PaymentAttemptEventRecord
from intentra.models.payment_checkout_approval import PaymentCheckoutApprovalRecord
from intentra.models.payment_reservation import PaymentReservationRecord
from intentra.routes.auth import current_user
from intentra.schemas.payments import (
    CheckoutApprovalRequest, CheckoutApprovalResponse,
    CheckoutReturnRequest, CheckoutVerificationResponse,
    PaymentCaptureResponse, PaymentReconciliationResponse,
    PaymentCheckoutLaunchResponse, PaymentAttemptHistoryItem,
    PaymentAttemptHistoryResponse, PaymentAttemptDetailResponse,
    PaymentAttemptEventItem,
    PaymentReservationHistoryItem, PaymentReservationHistoryResponse,
    PaymentEvaluationRequest,
    PaymentEvaluationResponse,
    PaymentEvaluationHistoryItem,
    PaymentEvaluationHistoryResponse,
    PaymentReservationRequest,
    PaymentReservationResponse,
)
from intentra.services.checkout_approval import (
    CheckoutApprovalError, initiate_checkout_approval, verify_checkout_return,
    cancel_checkout,
)
from intentra.services.payment_orchestration import (
    PaymentOrchestrationError, create_payment_order,
)
from intentra.services.payment_execution import ExecutionClaimError
from intentra.services.merchant_registry import MerchantRegistryError
from intentra.services.paypal_sandbox import (
    PayPalOrderNotSubmittedError, PayPalOrderOutcomeUnknownError,
    PayPalOrderRejectedError, PayPalSandboxError,
)
from intentra.services.payment_capture import (
    PaymentCaptureError, capture_approved_payment,
)
from intentra.services.payment_reconciliation import PaymentReconciliationError
from intentra.services.payment_reconciliation_runner import reconcile_payment_attempt
from intentra.services.authorization import (
    IntentContract,
    PaymentProposal,
    authorize,
)
from intentra.services.payment_reservation import PaymentReservationError, reserve_payment_locked

router = APIRouter(prefix="/api/payments", tags=["Payments"])
logger = logging.getLogger(__name__)
CORRELATION_HEADER = "X-Intentra-Correlation-ID"


def _checkout_error(status_code: int, code: str, message: str, *,
                    reservation_id: uuid.UUID | None = None,
                    correlation_id: str | None = None) -> HTTPException:
    """Return a stable public error and log only safe correlation metadata."""
    logger.warning("checkout_request_failed", extra={
        "event_name": "checkout_request_failed",
        "error_code": code,
        "http_status": status_code,
        "reservation_id": str(reservation_id) if reservation_id else None,
        "correlation_id": correlation_id,
    })
    return HTTPException(
        status_code=status_code,
        detail=message,
        headers={"X-Intentra-Error-Code": code,
                 **({CORRELATION_HEADER: correlation_id} if correlation_id else {})},
    )


async def checkout_provider(request: Request):
    try:
        from intentra.services.provider_runtime import build_checkout_providers
        registry, paypal, http = build_checkout_providers()
    except Exception as exc:
        logger.warning("checkout_provider_unavailable", extra={
            "event_name": "checkout_provider_unavailable",
            "error_code": "CHECKOUT_PROVIDER_UNAVAILABLE",
            "correlation_id": getattr(request.state, "correlation_id", None),
        })
        raise HTTPException(
            status_code=503,
            detail="PayPal Sandbox checkout is not configured or available.",
            headers={"X-Intentra-Error-Code": "CHECKOUT_PROVIDER_UNAVAILABLE"},
        ) from exc
    try:
        yield registry, paypal
    finally:
        await http.aclose()


def _frontend_origin() -> str:
    origin = os.getenv("INTENTRA_FRONTEND_URL", "http://localhost:3000").rstrip("/")
    parsed = urlsplit(origin)
    if (parsed.scheme not in {"https", "http"} or not parsed.netloc
        or parsed.username is not None or parsed.password is not None
        or parsed.query or parsed.fragment
        or (parsed.scheme == "http" and parsed.hostname not in {"localhost", "127.0.0.1"})):
        raise HTTPException(
            status_code=503,
            detail="Checkout origin configuration is invalid.",
            headers={"X-Intentra-Error-Code": "CHECKOUT_CONFIGURATION_INVALID"},
        )
    return origin


@router.post("/reservations/{reservation_id}/checkout", response_model=PaymentCheckoutLaunchResponse, status_code=201)
async def launch_payment_checkout(reservation_id: uuid.UUID,
                                 request: Request,
                                 user: UserRecord = Depends(current_user),
                                 provider=Depends(checkout_provider),
                                 db: AsyncSession = Depends(get_db)):
    registry, paypal = provider
    actor_id = user.id
    correlation_id = getattr(request.state, "correlation_id", None)
    await db.rollback()
    try:
        origin = _frontend_origin()
        launch = await create_payment_order(db, reservation_id=reservation_id,
            actor_id=actor_id, registry=registry, paypal=paypal,
            return_url=f"{origin}/checkout/return",
            cancel_url=f"{origin}/checkout/cancel")
        handoff = await initiate_checkout_approval(db, attempt_id=launch.attempt_id,
            actor_id=actor_id, registry=registry, paypal=paypal)
    except PaymentOrchestrationError as exc:
        raise _checkout_error(exc.status_code, exc.code,
            "Checkout requires review before another attempt.", reservation_id=reservation_id,
            correlation_id=correlation_id) from exc
    except (ExecutionClaimError,):
        raise _checkout_error(409, "PAYMENT_NOT_ELIGIBLE",
            "Payment is not eligible for checkout. No new provider request was submitted.",
            reservation_id=reservation_id, correlation_id=correlation_id)
    except CheckoutApprovalError:
        raise _checkout_error(503, "CHECKOUT_HANDOFF_INCOMPLETE",
            "A PayPal order may already exist, but the secure checkout handoff was not completed. Do not retry; review payment history and provider activity.",
            reservation_id=reservation_id, correlation_id=correlation_id)
    except MerchantRegistryError:
        raise _checkout_error(503, "PROVIDER_NOT_SUBMITTED",
            "Trusted merchant validation failed before the PayPal order request. Review configuration before retrying.",
            reservation_id=reservation_id, correlation_id=correlation_id)
    except PayPalOrderNotSubmittedError as exc:
        raise _checkout_error(503, "PROVIDER_NOT_SUBMITTED",
            "PayPal order creation was not submitted. Review payment history before retrying.",
            reservation_id=reservation_id, correlation_id=correlation_id) from exc
    except PayPalOrderRejectedError as exc:
        raise _checkout_error(502, "PROVIDER_REJECTED",
            "PayPal explicitly rejected the order request. Review payment history and correct the issue before another attempt.",
            reservation_id=reservation_id, correlation_id=correlation_id) from exc
    except PayPalOrderOutcomeUnknownError as exc:
        raise _checkout_error(503, "PROVIDER_OUTCOME_UNKNOWN",
            "PayPal may have accepted the order. Do not retry; review payment history and provider activity.",
            reservation_id=reservation_id, correlation_id=correlation_id) from exc
    except PayPalSandboxError as exc:
        raise _checkout_error(503, "ORDER_LOOKUP_UNAVAILABLE",
            "INTENTRA could not verify the existing PayPal order. Do not create another order; review payment history.",
            reservation_id=reservation_id, correlation_id=correlation_id) from exc
    except HTTPException as exc:
        logger.warning("checkout_preflight_rejected", extra={
            "event_name": "checkout_preflight_rejected",
            "error_code": (exc.headers or {}).get("X-Intentra-Error-Code", "CHECKOUT_PREFLIGHT_REJECTED"),
            "http_status": exc.status_code,
            "reservation_id": str(reservation_id),
            "correlation_id": correlation_id,
        })
        raise
    except Exception as exc:
        # Database or application failures can occur after provider acceptance.
        # Without durable stage evidence, classify conservatively.
        raise _checkout_error(503, "CHECKOUT_STATE_UNCERTAIN",
            "Checkout could not be confirmed. A PayPal order may exist. Do not retry until payment history and provider activity are reviewed.",
            reservation_id=reservation_id, correlation_id=correlation_id) from exc
    return PaymentCheckoutLaunchResponse(
        approval_id=handoff.approval_id, attempt_id=handoff.attempt_id,
        provider_order_id=handoff.provider_order_id,
        return_state=handoff.return_state, expires_at=handoff.expires_at,
        state="PENDING", approval_url=launch.approval_url)


@router.post("/checkout", response_model=CheckoutApprovalResponse, status_code=201)
async def create_checkout(payload: CheckoutApprovalRequest,
                          user: UserRecord = Depends(current_user),
                          provider=Depends(checkout_provider),
                          db: AsyncSession = Depends(get_db)):
    registry, paypal = provider
    try:
        actor_id = user.id
        # current_user performs a read using this same session. End its
        # read-only autobegun transaction before the service opens its own.
        await db.rollback()
        result = await initiate_checkout_approval(db, attempt_id=payload.attempt_id,
            actor_id=actor_id, registry=registry, paypal=paypal)
    except CheckoutApprovalError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    return CheckoutApprovalResponse(approval_id=result.approval_id,
        attempt_id=result.attempt_id, provider_order_id=result.provider_order_id,
        return_state=result.return_state, expires_at=result.expires_at, state="PENDING")


@router.post("/checkout/return", response_model=CheckoutVerificationResponse)
async def checkout_return(payload: CheckoutReturnRequest,
                          user: UserRecord = Depends(current_user),
                          provider=Depends(checkout_provider),
                          db: AsyncSession = Depends(get_db)):
    registry, paypal = provider
    try:
        actor_id = user.id
        await db.rollback()
        result = await verify_checkout_return(db, attempt_id=payload.attempt_id,
            actor_id=actor_id, return_state=payload.state,
            registry=registry, paypal=paypal)
    except CheckoutApprovalError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    return CheckoutVerificationResponse(approval_id=result.approval_id,
        attempt_id=result.attempt_id, state=result.state, verified_at=result.verified_at)


@router.post("/checkout/cancel", response_model=CheckoutVerificationResponse)
async def checkout_cancel(payload: CheckoutReturnRequest,
                          user: UserRecord = Depends(current_user),
                          db: AsyncSession = Depends(get_db)):
    try:
        await db.rollback()
        result = await cancel_checkout(db, attempt_id=payload.attempt_id,
            actor_id=user.id, return_state=payload.state)
    except CheckoutApprovalError as exc:
        raise HTTPException(status_code=409, detail="Checkout return is unavailable.") from exc
    return CheckoutVerificationResponse(approval_id=result.approval_id,
        attempt_id=result.attempt_id, state=result.state, verified_at=result.verified_at)


def _attempt_history_item(attempt, reservation, approval):
    return PaymentAttemptHistoryItem(
        attempt_id=attempt.id, reservation_id=reservation.id,
        contract_id=reservation.contract_id, provider_order_id=attempt.provider_order_id,
        capture_id=attempt.capture_id, attempt_state=attempt.status,
        reservation_state=reservation.status,
        approval_state=approval.state if approval else None,
        approval_expires_at=approval.expires_at if approval else None,
        approval_consumed_at=approval.consumed_at if approval else None,
        merchant_id=reservation.merchant_id, amount=reservation.amount,
        currency=reservation.currency, created_at=attempt.created_at,
        updated_at=attempt.updated_at)


@router.get("/history", response_model=PaymentAttemptHistoryResponse)
async def payment_history(user: UserRecord = Depends(current_user), db: AsyncSession = Depends(get_db)):
    rows = (await db.execute(
        select(PaymentAttemptRecord, PaymentReservationRecord, PaymentCheckoutApprovalRecord)
        .join(PaymentReservationRecord, PaymentReservationRecord.id == PaymentAttemptRecord.reservation_id)
        .outerjoin(PaymentCheckoutApprovalRecord, PaymentCheckoutApprovalRecord.attempt_id == PaymentAttemptRecord.id)
        .where(PaymentReservationRecord.actor_id == user.id)
        .order_by(PaymentAttemptRecord.created_at.desc(), PaymentAttemptRecord.id.desc())
        .limit(100))).all()
    return PaymentAttemptHistoryResponse(items=[_attempt_history_item(*row) for row in rows])


@router.get("/reservations", response_model=PaymentReservationHistoryResponse)
async def payment_reservations(user: UserRecord = Depends(current_user), db: AsyncSession = Depends(get_db)):
    reservations = (await db.scalars(select(PaymentReservationRecord)
        .where(PaymentReservationRecord.actor_id == user.id)
        .order_by(PaymentReservationRecord.created_at.desc(), PaymentReservationRecord.id.desc())
        .limit(100))).all()
    return PaymentReservationHistoryResponse(items=[PaymentReservationHistoryItem(
        reservation_id=r.id, contract_id=r.contract_id, merchant_id=r.merchant_id,
        amount=r.amount, currency=r.currency, status=r.status, reason=r.reason,
        created_at=r.created_at) for r in reservations])


@router.get("/attempts/{attempt_id}", response_model=PaymentAttemptDetailResponse)
async def payment_attempt_detail(attempt_id: uuid.UUID, user: UserRecord = Depends(current_user),
                                 db: AsyncSession = Depends(get_db)):
    row = await db.execute(
        select(PaymentAttemptRecord, PaymentReservationRecord, PaymentCheckoutApprovalRecord)
        .join(PaymentReservationRecord, PaymentReservationRecord.id == PaymentAttemptRecord.reservation_id)
        .outerjoin(PaymentCheckoutApprovalRecord, PaymentCheckoutApprovalRecord.attempt_id == PaymentAttemptRecord.id)
        .where(PaymentAttemptRecord.id == attempt_id, PaymentReservationRecord.actor_id == user.id))
    records = row.one_or_none()
    if records is None:
        raise HTTPException(status_code=404, detail="Payment attempt not found")
    attempt, reservation, approval = records
    events = (await db.scalars(select(PaymentAttemptEventRecord)
        .where(PaymentAttemptEventRecord.attempt_id == attempt_id)
        .order_by(PaymentAttemptEventRecord.created_at, PaymentAttemptEventRecord.id))).all()
    return PaymentAttemptDetailResponse(
        **_attempt_history_item(attempt, reservation, approval).model_dump(),
        approval_verified_at=approval.verified_at if approval else None,
        events=[PaymentAttemptEventItem(event_type=e.event_type,
            event_correlation_id=e.event_correlation_id, event_data=e.event_data,
            created_at=e.created_at) for e in events])


@router.post("/attempts/{attempt_id}/capture", response_model=PaymentCaptureResponse)
async def capture_payment(attempt_id: uuid.UUID,
                          user: UserRecord = Depends(current_user),
                          provider=Depends(checkout_provider),
                          db: AsyncSession = Depends(get_db)):
    registry, paypal = provider
    actor_id = user.id
    await db.rollback()
    try:
        result = await capture_approved_payment(db, attempt_id=attempt_id,
            actor_id=actor_id, registry=registry, paypal=paypal)
    except PaymentCaptureError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    return PaymentCaptureResponse(attempt_id=result.attempt_id,
        state=result.state, capture_id=result.capture_id, action=result.action)


@router.post("/attempts/{attempt_id}/reconcile", response_model=PaymentReconciliationResponse)
async def reconcile_payment(attempt_id: uuid.UUID,
                            user: UserRecord = Depends(current_user),
                            provider=Depends(checkout_provider),
                            db: AsyncSession = Depends(get_db)):
    registry, paypal = provider
    actor_id = user.id
    await db.rollback()
    try:
        result = await reconcile_payment_attempt(db, attempt_id=attempt_id,
            actor_id=actor_id, registry=registry, paypal=paypal)
    except PaymentReconciliationError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    except PaymentCaptureError as exc:
        raise HTTPException(status_code=409, detail="Payment state changed; reconciliation is required.") from exc
    return PaymentReconciliationResponse(attempt_id=result.attempt_id,
        action=result.action, provider_order_id=result.provider_order_id,
        provider_status=result.provider_status, capture_id=result.capture_id)


@router.post(
    "/evaluate",
    response_model=PaymentEvaluationResponse,
)
async def evaluate_payment(
    payload: PaymentEvaluationRequest,
    user: UserRecord = Depends(current_user),
    db: AsyncSession = Depends(get_db),
):
    actor_id = user.id

    contract = await db.scalar(
        select(IntentContractRecord).where(
            IntentContractRecord.id == payload.contract_id,
            IntentContractRecord.owner_id == actor_id,
        )
    )

    if contract is None:
        raise HTTPException(
            status_code=404,
            detail="Contract not found",
        )

    result = authorize(
        IntentContract(
            merchant_id=contract.merchant_id,
            maximum_amount=contract.maximum_amount,
            currency=contract.currency,
            approved=contract.status == "APPROVED",
        ),
        PaymentProposal(
            merchant_id=payload.merchant_id,
            amount=payload.amount,
            currency=payload.currency,
        ),
    )

    evaluation = PaymentEvaluationRecord(
        contract_id=contract.id,
        actor_id=actor_id,
        contract_version=contract.version,
        merchant_id=payload.merchant_id,
        amount=payload.amount,
        currency=payload.currency,
        decision=result.decision.value,
        reason=result.reason,
    )

    db.add(evaluation)
    await db.commit()
    await db.refresh(evaluation)

    return PaymentEvaluationResponse(
        evaluation_id=evaluation.id,
        contract_id=contract.id,
        contract_version=contract.version,
        decision=evaluation.decision,
        reason=evaluation.reason,
    )


@router.get(
    "/evaluations",
    response_model=PaymentEvaluationHistoryResponse,
)
async def list_payment_evaluations(
    contract_id: uuid.UUID,
    user: UserRecord = Depends(current_user),
    db: AsyncSession = Depends(get_db),
):
    contract = await db.scalar(
        select(IntentContractRecord).where(
            IntentContractRecord.id == contract_id,
            IntentContractRecord.owner_id == user.id,
        )
    )

    if contract is None:
        raise HTTPException(
            status_code=404,
            detail="Contract not found",
        )

    evaluations = (
        await db.scalars(
            select(PaymentEvaluationRecord)
            .where(
                PaymentEvaluationRecord.contract_id == contract_id,
                PaymentEvaluationRecord.actor_id == user.id,
            )
            .order_by(
                PaymentEvaluationRecord.created_at.desc(),
                PaymentEvaluationRecord.id.desc(),
            )
            .limit(100)
        )
    ).all()

    return PaymentEvaluationHistoryResponse(
        items=[
            PaymentEvaluationHistoryItem(
                evaluation_id=record.id,
                contract_id=record.contract_id,
                contract_version=record.contract_version,
                merchant_id=record.merchant_id,
                amount=record.amount,
                currency=record.currency,
                decision=record.decision,
                reason=record.reason,
                created_at=record.created_at,
            )
            for record in evaluations
        ]
    )


@router.post(
    "/reserve",
    response_model=PaymentReservationResponse,
)
async def reserve_payment(
    payload: PaymentReservationRequest,
    user: UserRecord = Depends(current_user),
    db: AsyncSession = Depends(get_db),
):
    actor_id = user.id

    # Serialize reservations and revocation against this contract.
    contract = await db.scalar(
        select(IntentContractRecord)
        .where(
            IntentContractRecord.id == payload.contract_id,
            IntentContractRecord.owner_id == actor_id,
        )
        .with_for_update()
    )

    if contract is None:
        raise HTTPException(status_code=404, detail="Contract not found")

    try:
        reservation, remaining, _ = await reserve_payment_locked(
            db,
            contract=contract,
            actor_id=actor_id,
            idempotency_key=payload.idempotency_key,
            merchant_id=payload.merchant_id,
            amount=payload.amount,
            currency=payload.currency,
        )
    except PaymentReservationError as exc:
        raise HTTPException(status_code=exc.status_code, detail=str(exc)) from exc

    await db.commit()
    await db.refresh(reservation)

    return PaymentReservationResponse(
        reservation_id=reservation.id,
        contract_id=reservation.contract_id,
        contract_version=reservation.contract_version,
        status=reservation.status,
        reason=reservation.reason,
        remaining_amount=remaining,
    )
