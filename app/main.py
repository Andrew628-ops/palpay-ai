from fastapi import FastAPI
from app.database import engine
from app.models import Base
Base.metadata.create_all(bind=engine)
from app.routers.rules import router as payment_router
from app.routers.ai_review import router as ai_review_router
from app.routers.payouts import router as payout_router

app = FastAPI(title="PalPay AI API", description="API for managing SmartPay automated payment rules", version="1.0.0")

app.include_router(payment_router, prefix="/api/rules", tags=["smartpay"])
app.include_router(ai_review_router, prefix="/api/rules", tags=["smartpay"])
app.include_router(payout_router, prefix="/api/rules", tags=["PayPal Payments"])