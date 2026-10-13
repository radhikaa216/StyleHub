from fastapi import FastAPI

from app.config import settings
from app.database import Base, engine
from app.models import User
from app.routes.auth import router as auth_router
from app.routes.products import router as products_router
from app.routes.cart import router as cart_router
from app.routes.orders import router as orders_router
from app.routes.admin_orders import router as admin_orders_router
from app.routes.payments import router as payments_router
Base.metadata.create_all(bind=engine)


app = FastAPI(
    title=settings.APP_NAME
)


app.include_router(auth_router)
app.include_router(products_router)
app.include_router(cart_router)
app.include_router(orders_router)
app.include_router(admin_orders_router)
app.include_router(payments_router)

@app.get("/")
def root():
    return {"message": "Welcome to StyleHub API"}