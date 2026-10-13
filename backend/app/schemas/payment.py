
from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel


class PaymentResponse(BaseModel):
    id: int
    order_id: int
    amount: Decimal
    currency: str
    status: str
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class PaymentSessionResponse(BaseModel):
    payment_id: int
    order_id: int
    checkout_url: str
    session_id: str
