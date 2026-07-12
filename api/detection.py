# detection.py
import pandas as pd
from pydantic import BaseModel


class CampaignAlert(BaseModel):
    campaign_id: str
    campaign_name: str
    platform: str
    roas: float
    platform_avg_roas: float
    pct_below_average: float
    recommendation: str


def detect_underperformers(df: pd.DataFrame, std_threshold: float = 1.0) -> list[CampaignAlert]:
    """
    Expects df to already contain 'roas', 'platform_mean_roas', and
    'platform_stddev_roas' columns, as computed by the campaign_metrics
    SQL view. This function applies only the alerting policy (threshold +
    labeling) — the statistics themselves are computed in SQL for
    consistency with the rest of the pipeline.
    """
    df = df.copy()

    # guard against Decimal types from SQLAlchemy
    for col in ("roas", "platform_mean_roas", "platform_stddev_roas"):
        df[col] = df[col].astype(float)

    # single-campaign platforms have NULL/NaN stddev from SQL — treat as 0
    df["platform_stddev_roas"] = df["platform_stddev_roas"].fillna(0)

    underperformers = df[
        df["roas"] < (df["platform_mean_roas"] - std_threshold * df["platform_stddev_roas"])
    ]

    alerts = []
    for _, row in underperformers.iterrows():
        mean = row["platform_mean_roas"]
        if mean == 0:
            pct_below = 0.0  # avoid div-by-zero / nonsensical negative-mean math
        else:
            pct_below = ((mean - row["roas"]) / mean) * 100

        alerts.append(
            CampaignAlert(
                campaign_id=row["campaign_id"],
                campaign_name=row["campaign_name"],
                platform=row["platform"],
                roas=round(row["roas"], 3),
                platform_avg_roas=round(mean, 3),
                pct_below_average=round(pct_below, 1),
                recommendation=(
                    f"ROAS is {pct_below:.0f}% below {row['platform']} average. "
                    f"Consider pausing or reallocating budget."
                ),
            )
        )
    return alerts