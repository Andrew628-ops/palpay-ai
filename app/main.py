from fastapi import FastAPI
from app.database import engine
from app.models import Base
Base.metadata.create_all(bind=engine)
from app.routers.rules import router as payment_router

app = FastAPI()

app.include_router(payment_router, prefix="/api/rules", tags=["smartpay"])