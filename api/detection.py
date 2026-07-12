# detection.py
import pandas as pd
from pydantic import BaseModel


class CampaignAlert(BaseModel):
    campaign_id: str
    campaign_name: str
    platform: str
    roas: float
    platform_roas_percentile: float
    recommendation: str


def detect_underperformers(df: pd.DataFrame, bottom_pct: float = 0.02) -> list[CampaignAlert]:
    """
    Flags campaigns in the bottom `bottom_pct` of ROAS within their platform.
    Expects df to already contain 'roas' and 'platform_roas_percentile' columns,
    as computed by the campaign_metrics SQL view.

    Percentile rank is used instead of mean/std because ROAS is heavily
    right-skewed (a small number of outlier campaigns inflate standard
    deviation to the point that mean - std can go negative, making std-based
    thresholds meaningless).
    """
    df = df.copy()
    df["roas"] = df["roas"].astype(float)
    df["platform_roas_percentile"] = df["platform_roas_percentile"].astype(float)

    underperformers = df[df["platform_roas_percentile"] <= bottom_pct]

    alerts = []
    for _, row in underperformers.iterrows():
        pct_rank = row["platform_roas_percentile"] * 100
        alerts.append(
            CampaignAlert(
                campaign_id=row["campaign_id"],
                campaign_name=row["campaign_name"],
                platform=row["platform"],
                roas=round(row["roas"], 3),
                platform_roas_percentile=round(row["platform_roas_percentile"], 4),
                recommendation=(
                    f"ROAS is in the bottom {pct_rank:.1f}% of {row['platform']} campaigns. "
                    f"Consider pausing or reallocating budget."
                ),
            )
        )
    return alerts