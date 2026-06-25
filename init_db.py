# init_db.py
import os
import pandas as pd
from sqlalchemy import create_engine, types

DATABASE_URL = os.environ["DATABASE_URL"]
engine = create_engine(DATABASE_URL)

df = pd.read_csv("data/synthetic_social_media_campaign_data.csv")

df["post_date"] = pd.to_datetime(df["post_date"], format="%m/%d/%Y").dt.date
df["post_time"] = pd.to_datetime(df["post_time"], format="%H:%M").dt.time

df.to_sql(
    name="campaigns",
    con=engine,
    if_exists="replace",
    index=False,
    dtype={
        "campaign_id":           types.Text,
        "campaign_name":         types.Text,
        "platform":              types.Text,
        "post_type":             types.Text,
        "post_date":             types.Date,
        "post_time":             types.Time,
        "content_theme":         types.Text,
        "target_audience":       types.Text,
        "boosted_post":          types.Boolean,
        "spend_usd":             types.Numeric(10, 2),
        "reach":                 types.BigInteger,
        "impressions":           types.BigInteger,
        "engagements":           types.BigInteger,
        "clicks":                types.BigInteger,
        "conversions":           types.BigInteger,
        "conversion_value_usd":  types.Numeric(10, 2),
        "cpc_usd":               types.Numeric(10, 4),
        "ctr":                   types.Numeric(10, 4),
        "engagement_rate":       types.Numeric(10, 4),
        "hashtag_count":         types.Integer,
        "emoji_count":           types.Integer,
        "word_count":            types.Integer,
        "sentiment_score":       types.Numeric(5, 4),
        "video_length_seconds":  types.Integer,
    }
)

print(f"Loaded {len(df)} rows into campaigns table.")