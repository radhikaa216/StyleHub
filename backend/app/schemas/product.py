
from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, Field, ConfigDict

class ProductCreate(BaseModel):
    name: str = Field(min_length=2, max_length=150)
    description: str | None = None
    price: Decimal = Field(gt=0, max_digits=10, decimal_places=2)
    image_url: str | None = Field(default=None, max_length=500)
    stock: int = Field(default=0, ge=0)


class ProductResponse(BaseModel):
    id: int
    name: str
    description: str | None
    price: Decimal
    image_url: str | None
    stock: int
    is_active: bool
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)



class ProductUpdate(BaseModel):
    name: str | None = Field(
        default=None,
        min_length=2,
        max_length=150
    )
    description: str | None = None
    price: Decimal | None = Field(
        default=None,
        gt=0,
        max_digits=10,
        decimal_places=2
    )
    image_url: str | None = Field(
        default=None,
        max_length=500
    )
    stock: int | None = Field(
        default=None,
        ge=0
    )

