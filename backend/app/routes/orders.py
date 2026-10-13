
from decimal import Decimal
from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.database import get_db
from app.dependencies.auth import get_current_user
from app.models.cart import CartItem
from app.models.order import Order, OrderItem
from app.models.product import Product
from app.models.user import User
import stripe
from app.config import settings
from app.models.payment import Payment
from app.schemas.order import OrderItemResponse, OrderResponse


router = APIRouter(prefix="/orders", tags=["Orders"])


@router.post(
    "/checkout",
    response_model=OrderResponse,
    status_code=status.HTTP_201_CREATED,
)
def checkout(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    try:
        # 1. Get the logged-in user's cart.
        cart_items = (
            db.query(CartItem)
            .filter(CartItem.user_id == current_user.id)
            .order_by(CartItem.product_id)
            .all()
        )

        if not cart_items:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Your cart is empty",
            )

        # 2. Lock the relevant product rows while checking stock.
        order_lines = []
        total_amount = Decimal("0.00")

        for cart_item in cart_items:
            product = (
                db.query(Product)
                .filter(Product.id == cart_item.product_id)
                .with_for_update()
                .first()
            )

            if product is None or not product.is_active:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Product ID {cart_item.product_id} is unavailable",
                )

            if cart_item.quantity > product.stock:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=(
                        f"Insufficient stock for {product.name}. "
                        f"Available stock: {product.stock}"
                    ),
                )

            unit_price = Decimal(str(product.price))
            subtotal = unit_price * cart_item.quantity
            total_amount += subtotal

            order_lines.append(
                {
                    "cart_item": cart_item,
                    "product": product,
                    "product_name": product.name,
                    "unit_price": unit_price,
                    "quantity": cart_item.quantity,
                    "subtotal": subtotal,
                }
            )

        # 3. Create the order.
        order = Order(
            order_number=f"SH-{uuid4().hex[:16].upper()}",
            user_id=current_user.id,
            total_amount=total_amount,
            status="pending",
        )

        db.add(order)
        db.flush()

        # 4. Save order items and reduce stock.
        response_items = []

        for line in order_lines:
            product = line["product"]

            order_item = OrderItem(
                order_id=order.id,
                product_id=product.id,
                product_name=line["product_name"],
                unit_price=line["unit_price"],
                quantity=line["quantity"],
                subtotal=line["subtotal"],
            )

            db.add(order_item)
            product.stock -= line["quantity"]

            response_items.append(
                {
                    "id": None,
                    "product_id": product.id,
                    "product_name": line["product_name"],
                    "unit_price": line["unit_price"],
                    "quantity": line["quantity"],
                    "subtotal": line["subtotal"],
                }
            )

        # 5. Remove purchased items from the cart.
        for line in order_lines:
            db.delete(line["cart_item"])

        # 6. Commit all changes together.
        db.flush()
        db.refresh(order)

        # Fetch generated order-item IDs before committing.
        db.flush()
        saved_items = (
            db.query(OrderItem)
            .filter(OrderItem.order_id == order.id)
            .order_by(OrderItem.id)
            .all()
        )

        db.commit()

        return OrderResponse(
            id=order.id,
            order_number=order.order_number,
            total_amount=order.total_amount,
            status=order.status,
            created_at=order.created_at,
            updated_at=order.updated_at,
            items=[
                OrderItemResponse(
                    id=item.id,
                    product_id=item.product_id,
                    product_name=item.product_name,
                    unit_price=item.unit_price,
                    quantity=item.quantity,
                    subtotal=item.subtotal,
                )
                for item in saved_items
            ],
        )

    except HTTPException:
        db.rollback()
        raise
    except Exception:
        db.rollback()
        raise


@router.get("/", response_model=list[OrderResponse])
def get_order_history(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    orders = (
        db.query(Order)
        .filter(Order.user_id == current_user.id)
        .order_by(Order.created_at.desc())
        .all()
    )

    result = []

    for order in orders:
        order_items = (
            db.query(OrderItem)
            .filter(OrderItem.order_id == order.id)
            .order_by(OrderItem.id)
            .all()
        )

        result.append(
            OrderResponse(
                id=order.id,
                order_number=order.order_number,
                total_amount=order.total_amount,
                status=order.status,
                created_at=order.created_at,
                updated_at=order.updated_at,
                items=[
                    OrderItemResponse(
                        id=item.id,
                        product_id=item.product_id,
                        product_name=item.product_name,
                        unit_price=item.unit_price,
                        quantity=item.quantity,
                        subtotal=item.subtotal,
                    )
                    for item in order_items
                ],
            )
        )

    return result


@router.get("/{order_id}", response_model=OrderResponse)
def get_order_details(
    order_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
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

    order_items = (
        db.query(OrderItem)
        .filter(OrderItem.order_id == order.id)
        .order_by(OrderItem.id)
        .all()
    )

    return OrderResponse(
        id=order.id,
        order_number=order.order_number,
        total_amount=order.total_amount,
        status=order.status,
        created_at=order.created_at,
        updated_at=order.updated_at,
        items=[
            OrderItemResponse(
                id=item.id,
                product_id=item.product_id,
                product_name=item.product_name,
                unit_price=item.unit_price,
                quantity=item.quantity,
                subtotal=item.subtotal,
            )
            for item in order_items
        ],
    )



@router.post("/{order_id}/cancel", response_model=OrderResponse)
def cancel_order(
    order_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    try:
        # 1. Find and lock the order belonging to this user.
        order = (
            db.query(Order)
            .filter(
                Order.id == order_id,
                Order.user_id == current_user.id,
            )
            .with_for_update()
            .first()
        )

        if order is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Order not found",
            )

        # 2. Only pending or confirmed orders can be cancelled.
        if order.status not in ("pending", "confirmed"):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=(
                    f"Order cannot be cancelled because its "
                    f"status is '{order.status}'"
                ),
            )

        # 3. Load payment records for this order.
        payments = (
            db.query(Payment)
            .filter(Payment.order_id == order.id)
            .with_for_update()
            .all()
        )

        paid_payments = [
            payment for payment in payments
            if payment.status == "paid"
        ]

        if len(paid_payments) > 1:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=(
                    "Multiple successful payments exist for this order. "
                    "Manual review is required before cancellation."
                ),
            )

        paid_payment = paid_payments[0] if paid_payments else None

        # 4. Refund a successful payment before cancelling the order.
        if paid_payment is not None:
            if not paid_payment.stripe_payment_intent_id:
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail=(
                        "Payment has no Stripe PaymentIntent ID. "
                        "The order cannot be cancelled automatically."
                    ),
                )

            stripe_key = settings.STRIPE_SECRET_KEY

            if not stripe_key or not stripe_key.startswith("sk_test_"):
                raise HTTPException(
                    status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                    detail=(
                        "Stripe test secret key is not configured."
                    ),
                )

            stripe.api_key = stripe_key

            try:
                refund = stripe.Refund.create(
                    payment_intent=paid_payment.stripe_payment_intent_id,
                    idempotency_key=f"stylehub-order-{order.id}-refund",
                    metadata={
                        "order_id": str(order.id),
                        "payment_id": str(paid_payment.id),
                    },
                )

            except stripe.StripeError as exc:
                db.rollback()
                raise HTTPException(
                    status_code=status.HTTP_502_BAD_GATEWAY,
                    detail=(
                        "Stripe could not process the refund. "
                        "The order was not cancelled."
                    ),
                ) from exc

            # Do not cancel the order if Stripe has not completed
            # the refund successfully.
            if refund.status != "succeeded":
                db.rollback()
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail=(
                        f"Refund status is '{refund.status}'. "
                        "The order remains unchanged pending review."
                    ),
                )

            paid_payment.status = "refunded"

        # 5. Load order items.
        order_items = (
            db.query(OrderItem)
            .filter(OrderItem.order_id == order.id)
            .order_by(OrderItem.product_id)
            .all()
        )

        # 6. Lock products and validate they still exist.
        products = {}

        for item in order_items:
            product = (
                db.query(Product)
                .filter(Product.id == item.product_id)
                .with_for_update()
                .first()
            )

            if product is None:
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail=(
                        f"Cannot restore stock for product "
                        f"ID {item.product_id}. Manual review required."
                    ),
                )

            products[item.product_id] = product

        # 7. Restore stock and cancel the order.
        for item in order_items:
            product = products[item.product_id]
            product.stock += item.quantity

        order.status = "cancelled"

        # 8. Build the response and commit the database changes.
        response = OrderResponse(
            id=order.id,
            order_number=order.order_number,
            total_amount=order.total_amount,
            status=order.status,
            created_at=order.created_at,
            updated_at=order.updated_at,
            items=[
                OrderItemResponse(
                    id=item.id,
                    product_id=item.product_id,
                    product_name=item.product_name,
                    unit_price=item.unit_price,
                    quantity=item.quantity,
                    subtotal=item.subtotal,
                )
                for item in order_items
            ],
        )

        db.commit()

        return response

    except HTTPException:
        db.rollback()
        raise

    except Exception:
        db.rollback()
        raise
