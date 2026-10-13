
from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, Field


class OrderItemResponse(BaseModel):
    id: int
    product_id: int
    product_name: str
    unit_price: Decimal
    quantity: int
    subtotal: Decimal


class OrderResponse(BaseModel):
    id: int
    order_number: str
    total_amount: Decimal
    status: str
    created_at: datetime
    updated_at: datetime
    items: list[OrderItemResponse]


class OrderStatusUpdate(BaseModel):
    status: str = Field(
        pattern="^(pending|confirmed|processing|shipped|delivered|cancelled)$"
    )
