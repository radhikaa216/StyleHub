
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.database import get_db
from app.dependencies.auth import get_current_admin
from app.models.order import Order, OrderItem
from app.models.user import User
from app.models.payment import Payment
from app.schemas.order import (
    OrderItemResponse,
    OrderResponse,
    OrderStatusUpdate,
)

router = APIRouter(prefix="/admin/orders", tags=["Admin Orders"])


def build_order_response(db: Session, order: Order) -> OrderResponse:
    items = (
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
            for item in items
        ],
    )


@router.get("/", response_model=list[OrderResponse])
def get_all_orders(
    db: Session = Depends(get_db),
    current_admin: User = Depends(get_current_admin),
):
    orders = (
        db.query(Order)
        .order_by(Order.created_at.desc())
        .all()
    )

    return [
        build_order_response(db, order)
        for order in orders
    ]


@router.get("/{order_id}", response_model=OrderResponse)
def get_order_by_id(
    order_id: int,
    db: Session = Depends(get_db),
    current_admin: User = Depends(get_current_admin),
):
    order = db.query(Order).filter(Order.id == order_id).first()

    if order is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Order not found",
        )

    return build_order_response(db, order)


@router.patch(
    "/{order_id}/status",
    response_model=OrderResponse,
)

@router.patch(
    "/{order_id}/status",
    response_model=OrderResponse,
)
def update_order_status(
    order_id: int,
    status_data: OrderStatusUpdate,
    db: Session = Depends(get_db),
    current_admin: User = Depends(get_current_admin),):
    order = db.query(Order).filter(Order.id == order_id).first()

    if order is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Order not found",
        )

    allowed_transitions = {
        "pending": {"confirmed"},
        "confirmed": {"processing"},
        "processing": {"shipped"},
        "shipped": {"delivered"},
    }

    new_status = status_data.status

    # Validate the requested status transition.
    if new_status not in allowed_transitions.get(order.status, set()):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=(
                f"Cannot change order status from '{order.status}' "
                f"to '{new_status}'"
            ),
        )

    # An order can only be confirmed after successful payment.
    if new_status == "confirmed":
        paid_payment = (
            db.query(Payment)
            .filter(
                Payment.order_id == order.id,
                Payment.status == "paid",
            )
            .first()
        )

        if paid_payment is None:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=(
                    "Cannot confirm this order because payment "
                    "has not been completed."
                ),
            )

    try:
        order.status = new_status
        db.commit()
        db.refresh(order)

        return build_order_response(db, order)

    except Exception:
        db.rollback()
        raise
