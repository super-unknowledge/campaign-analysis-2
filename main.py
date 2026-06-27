import os
from fastapi import FastAPI
from pydantic import BaseModel
from sqlalchemy import create_engine, text
from sqlalchemy.exc import OperationalError

DATABASE_URL = os.environ["DATABASE_URL"]
engine = create_engine(DATABASE_URL)

app = FastAPI(title="Campaign Performance API")


class HealthResponse(BaseModel):
    status: str
    database: str

# Test with
# uv run --env-file .env.local fastapi dev main.py

@app.get("/health", response_model=HealthResponse)
def health_check():
    try:
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        return HealthResponse(status="ok", database="connected")
    except OperationalError:
        return HealthResponse(status="degraded", database="unreachable")  # change to return 503