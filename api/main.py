import os
from enum import Enum
from fastapi import FastAPI, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy import create_engine, text
from sqlalchemy.exc import OperationalError
import pandas as pd

from detection import CampaignAlert, detect_underperformers

DATABASE_URL = os.environ["DATABASE_URL"]
engine = create_engine(DATABASE_URL)

app = FastAPI(title="Social Analytics API")

METRICS_QUERY = "SELECT * FROM campaign_metrics"


# -----------------------------------------------------------------------------
# Build a Platform enum dynamically from the DB at startup, so /docs always
# reflects the actual data instead of a hardcoded list that can drift.
# -----------------------------------------------------------------------------
def _load_platform_enum() -> type[Enum]:
    with engine.connect() as conn:
        rows = conn.execute(text("SELECT DISTINCT platform FROM campaigns ORDER BY platform"))
        values = [r[0] for r in rows]
    if not values:
        raise RuntimeError("No platforms found in campaigns table — has init_db.py run?")
    return Enum("Platform", {v.upper().replace(" ", "_"): v for v in values})


Platform = _load_platform_enum()


class AlertsResponse(BaseModel):
    total_alerts: int
    alerts: list[CampaignAlert]


class HealthResponse(BaseModel):
    status: str
    database: str


@app.get("/health", response_model=HealthResponse)
def health_check():
    try:
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        return HealthResponse(status="ok", database="connected")
    except OperationalError:
        return HealthResponse(status="degraded", database="unreachable")


@app.get("/alerts", response_model=AlertsResponse)
def get_alerts(
    platform: Platform | None = Query(default=None, description="Filter by platform"),
    threshold: float = Query(default=1.0, ge=0, description="Std deviations below mean"),
):
    try:
        with engine.connect() as conn:
            df = pd.read_sql(text(METRICS_QUERY), conn)
    except OperationalError:
        raise HTTPException(status_code=503, detail="Database unreachable")

    if platform:
        df = df[df["platform"] == platform.value]

    alerts = detect_underperformers(df, std_threshold=threshold)
    return AlertsResponse(total_alerts=len(alerts), alerts=alerts)