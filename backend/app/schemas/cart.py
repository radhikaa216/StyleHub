
from datetime import datetime

from decimal import Decimal
from pydantic import BaseModel, Field


class CartItemCreate(BaseModel):
    product_id: int = Field(gt=0)
    quantity: int = Field(default=1, gt=0)


class CartItemUpdate(BaseModel):
    quantity: int = Field(gt=0)


class CartItemResponse(BaseModel):
    id: int
    product_id: int
    product_name: str
    quantity: int
    unit_price: Decimal
    subtotal: Decimal
    created_at: datetime
    updated_at: datetime


class CartResponse(BaseModel):
    items: list[CartItemResponse]
    total_items: int
    total_amount: Decimal
