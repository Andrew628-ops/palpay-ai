from fastapi import FastAPI
from app.database import engine
from app.models import Base
Base.metadata.create_all(bind=engine)
from app.routers.rules import router as payment_router
from app.routers.ai_review import router as ai_review_router
from app.routers.payouts import router as payout_router
from app.routers.webhooks import router as webhook_router
from app.routers.payment_history import router as history_router
from app.routers.review_queue import router as review_queue_router
from app.routers.submission_history import router as submission_history_router
from app.routers.human_review import router as human_review_router
from pathlib import Path
from fastapi.staticfiles import StaticFiles

app = FastAPI(title="PalPay AI API", description="API for managing SmartPay automated payment rules", version="1.0.0")

app.include_router(payment_router, prefix="/api/rules", tags=["smartpay"])
app.include_router(ai_review_router, prefix="/api/rules", tags=["smartpay"])
app.include_router(payout_router, prefix="/api/rules", tags=["PayPal Payments"])
app.include_router(webhook_router, prefix="/api/webhooks", tags=["PayPal Webhooks"])
app.include_router(history_router, prefix="/api/payments", tags=["Payment History"])
app.include_router(review_queue_router, prefix="/api/reviews", tags=["AI Review Management"])
app.include_router(submission_history_router, prefix="/api/rules", tags=["smartpay"])
app.include_router(human_review_router, prefix="/api/reviews", tags=["Human Review"])


frontend_dist = (
    Path(__file__).resolve().parent.parent
    / "frontend"
    / "dist"
)

if frontend_dist.is_dir():
    app.mount(
        "/",
        StaticFiles(directory=str(frontend_dist), html=True),
        name="frontend",
    )
