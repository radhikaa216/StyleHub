
from decimal import Decimal, ROUND_HALF_UP

import stripe
from fastapi import APIRouter, Depends, Header, HTTPException, Request, status
from sqlalchemy.orm import Session

from app.config import settings
from app.database import get_db
from app.dependencies.auth import get_current_user
from app.models.order import Order
from app.models.payment import Payment
from app.models.user import User


router = APIRouter(prefix="/payments", tags=["Payments"])



def _stripe_object_to_dict(obj):
    """Convert a Stripe SDK object into a regular Python dictionary."""
    if isinstance(obj, dict):
        return obj

    if hasattr(obj, "to_dict_recursive"):
        return obj.to_dict_recursive()

    if hasattr(obj, "to_dict"):
        return obj.to_dict()

    raise TypeError(
        f"Unsupported Stripe object type: {type(obj).__name__}"
    )



def _amount_to_paise(amount) -> int:
    """Convert an INR amount into the integer paise expected by Stripe."""
    return int(
        (Decimal(str(amount)) * Decimal("100")).quantize(
            Decimal("1"),
            rounding=ROUND_HALF_UP,
        )
    )


def _get_stripe_key():
    """Validate and configure the Stripe API key."""
    secret_key = settings.STRIPE_SECRET_KEY

    if not secret_key or not secret_key.startswith("sk_test_"):
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="A valid Stripe test secret key is not configured",
        )

    stripe.api_key = secret_key
    return secret_key


@router.post(
    "/orders/{order_id}/checkout-session",
    status_code=status.HTTP_201_CREATED,
)
def create_checkout_session(
    order_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Create a Stripe Checkout Session for the logged-in user's order.
    """

    _get_stripe_key()

    order = (
        db.query(Order)
        .filter(
            Order.id == order_id,
            Order.user_id == current_user.id,
        )
        .first()
    )

    if order is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Order not found",
        )

    if order.status not in ("pending", "confirmed"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="This order cannot be paid in its current status",
        )

    existing_paid_payment = (
        db.query(Payment)
        .filter(
            Payment.order_id == order.id,
            Payment.status == "paid",
        )
        .first()
    )

    if existing_paid_payment is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="This order has already been paid",
        )

    amount_paise = _amount_to_paise(order.total_amount)

    if amount_paise <= 0:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Order amount must be greater than zero",
        )

    payment = Payment(
        order_id=order.id,
        amount=Decimal(str(order.total_amount)),
        currency="inr",
        status="pending",
    )

    try:
        # Obtain the payment ID before creating the Stripe session.
        db.add(payment)
        db.flush()

        metadata = {
            "payment_id": str(payment.id),
            "order_id": str(order.id),
        }

        checkout_session = stripe.checkout.Session.create(
            mode="payment",
            line_items=[
                {
                    "price_data": {
                        "currency": "inr",
                        "product_data": {
                            "name": f"StyleHub Order {order.order_number}",
                        },
                        "unit_amount": amount_paise,
                    },
                    "quantity": 1,
                }
            ],
            metadata=metadata,
            payment_intent_data={
                "metadata": metadata,
            },
            success_url=(
                "http://localhost:5173/payment/success"
                "?session_id={CHECKOUT_SESSION_ID}"
            ),
            cancel_url="http://localhost:5173/payment/cancel",
        )

        payment.stripe_session_id = checkout_session.id
        db.commit()
        db.refresh(payment)

        return {
            "message": "Checkout session created successfully",
            "payment_id": payment.id,
            "order_id": order.id,
            "session_id": checkout_session.id,
            "checkout_url": checkout_session.url,
            "amount": str(payment.amount),
            "currency": payment.currency,
            "status": payment.status,
        }

    except stripe.StripeError as exc:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="Unable to create Stripe Checkout Session",
        ) from exc

    except Exception:
        db.rollback()
        raise


@router.post("/webhook")
async def stripe_webhook(
    request: Request,
    stripe_signature: str = Header(
        default=None,
        alias="Stripe-Signature",
    ),
    db: Session = Depends(get_db),
):
    """
    Receive and verify Stripe webhook events.

    Only verified Stripe events can update payment records.
    """

    webhook_secret = settings.STRIPE_WEBHOOK_SECRET

    if not webhook_secret or not webhook_secret.startswith("whsec_"):
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Stripe webhook secret is not configured",
        )

    if not stripe_signature:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Missing Stripe-Signature header",
        )

    payload = await request.body()

    # Verify the signature using the original request body.
    try:
        event = stripe.Webhook.construct_event(
            payload,
            stripe_signature,
            webhook_secret,
        )
    except (ValueError, stripe.SignatureVerificationError) as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid Stripe webhook signature or payload",
        ) from exc

    event_data = _stripe_object_to_dict(event)
    event_type = event_data.get("type")

    # Only process payment-related events handled by this endpoint.
    if event_type not in (
        "checkout.session.completed",
        "checkout.session.async_payment_succeeded",
        "checkout.session.async_payment_failed",
    ):
        return {"received": True}

    session_data = _stripe_object_to_dict(
        event_data["data"]["object"]
    )

    metadata = session_data.get("metadata") or {}
    payment_id = metadata.get("payment_id")
    order_id = metadata.get("order_id")
    session_id = session_data.get("id")

    # A simulated or unrelated Stripe event may not belong to a
    # StyleHub payment. Acknowledge it without changing any records.
    if not payment_id or not order_id or not session_id:
        return {"received": True}

    try:
        payment_id = int(payment_id)
        order_id = int(order_id)
    except (TypeError, ValueError) as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid payment metadata",
        ) from exc

    try:
        payment = (
            db.query(Payment)
            .filter(Payment.id == payment_id)
            .with_for_update()
            .first()
        )

        # Ignore events that do not correspond to a local payment.
        if payment is None:
            return {"received": True}

        if payment.order_id != order_id:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Payment order metadata mismatch",
            )

        if payment.stripe_session_id != session_id:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Checkout Session does not match payment",
            )

        # Never process an already-paid payment twice.
        if payment.status == "paid":
            return {"received": True}

        if event_type == "checkout.session.async_payment_failed":
            if payment.status == "pending":
                payment.status = "failed"
                db.commit()

            return {"received": True}

        # checkout.session.completed can occur before an asynchronous
        # payment is actually paid.
        if session_data.get("payment_status") != "paid":
            return {"received": True}

        order = (
            db.query(Order)
            .filter(Order.id == order_id)
            .first()
        )

        if order is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Order not found",
            )

        expected_amount = _amount_to_paise(payment.amount)
        actual_amount = session_data.get("amount_total")
        actual_currency = session_data.get("currency")

        if (
            actual_amount != expected_amount
            or actual_currency != payment.currency.lower()
        ):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Payment amount or currency mismatch",
            )

        payment_intent = session_data.get("payment_intent")

        # Stripe may return an ID string or an expanded object.
        if isinstance(payment_intent, dict):
            payment_intent = payment_intent.get("id")

        payment.stripe_payment_intent_id = payment_intent
        payment.status = "paid"

        # Keep payment status separate from order fulfillment status.
        db.commit()

        return {"received": True}

    except HTTPException:
        db.rollback()
        raise

    except Exception:
        db.rollback()
        raise
