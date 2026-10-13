
from decimal import Decimal

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.database import get_db
from app.dependencies.auth import get_current_user
from app.models.cart import CartItem
from app.models.product import Product
from app.models.user import User
from app.schemas.cart import (
    CartItemCreate,
    CartItemUpdate,
    CartItemResponse,
    CartResponse,
)

router = APIRouter(prefix="/cart", tags=["Cart"])


def build_cart_item_response(
    cart_item: CartItem,
    product: Product
) -> CartItemResponse:
    subtotal = product.price * cart_item.quantity

    return CartItemResponse(
        id=cart_item.id,
        product_id=product.id,
        product_name=product.name,
        quantity=cart_item.quantity,
        unit_price=product.price,
        subtotal=subtotal,
        created_at=cart_item.created_at,
        updated_at=cart_item.updated_at,
    )


@router.post(
    "/items",
    response_model=CartItemResponse,
    status_code=status.HTTP_201_CREATED,
)
def add_to_cart(
    item_data: CartItemCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    product = (
        db.query(Product)
        .filter(
            Product.id == item_data.product_id,
            Product.is_active.is_(True),
        )
        .first()
    )

    if product is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Product not found or inactive",
        )

    cart_item = (
        db.query(CartItem)
        .filter(
            CartItem.user_id == current_user.id,
            CartItem.product_id == product.id,
        )
        .first()
    )

    existing_quantity = cart_item.quantity if cart_item else 0
    new_quantity = existing_quantity + item_data.quantity

    if new_quantity > product.stock:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Only {product.stock} units are available",
        )

    try:
        if cart_item:
            cart_item.quantity = new_quantity
        else:
            cart_item = CartItem(
                user_id=current_user.id,
                product_id=product.id,
                quantity=item_data.quantity,
            )
            db.add(cart_item)

        db.commit()
        db.refresh(cart_item)

        return build_cart_item_response(cart_item, product)

    except Exception:
        db.rollback()
        raise


@router.get("/", response_model=CartResponse)
def get_cart(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    cart_items = (
        db.query(CartItem, Product)
        .join(Product, CartItem.product_id == Product.id)
        .filter(
            CartItem.user_id == current_user.id,
            Product.is_active.is_(True),
        )
        .order_by(CartItem.created_at.desc())
        .all()
    )

    items = [
        build_cart_item_response(cart_item, product)
        for cart_item, product in cart_items
    ]

    total_items = sum(item.quantity for item in items)
    total_amount = sum(
        (item.subtotal for item in items),
        Decimal("0.00"),
    )

    return CartResponse(
        items=items,
        total_items=total_items,
        total_amount=total_amount,
    )


@router.patch(
    "/items/{item_id}",
    response_model=CartItemResponse,
)
def update_cart_item(
    item_id: int,
    item_data: CartItemUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    cart_item = (
        db.query(CartItem)
        .filter(
            CartItem.id == item_id,
            CartItem.user_id == current_user.id,
        )
        .first()
    )

    if cart_item is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Cart item not found",
        )

    product = (
        db.query(Product)
        .filter(
            Product.id == cart_item.product_id,
            Product.is_active.is_(True),
        )
        .first()
    )

    if product is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Product not found or inactive",
        )

    if item_data.quantity > product.stock:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Only {product.stock} units are available",
        )

    try:
        cart_item.quantity = item_data.quantity
        db.commit()
        db.refresh(cart_item)

        return build_cart_item_response(cart_item, product)

    except Exception:
        db.rollback()
        raise


@router.delete("/items/{item_id}")
def remove_from_cart(
    item_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    cart_item = (
        db.query(CartItem)
        .filter(
            CartItem.id == item_id,
            CartItem.user_id == current_user.id,
        )
        .first()
    )

    if cart_item is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Cart item not found",
        )

    try:
        db.delete(cart_item)
        db.commit()

        return {
            "message": "Item removed from cart successfully",
            "item_id": item_id,
        }

    except Exception:
        db.rollback()
        raise
