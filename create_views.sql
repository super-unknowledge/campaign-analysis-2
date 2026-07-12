-- =============================================================================
-- views.sql
-- Derived metrics for the social analytics pipeline.
-- Run after init_db.py has loaded campaigns.csv into the campaigns table.
-- =============================================================================


-- -----------------------------------------------------------------------------
-- campaign_metrics
-- Row-level derived metrics. Mirrors the pandas logic from exploration.
-- Filtered to rows where spend > 0 AND conversions > 0 to avoid division by
-- zero and keep all ratios meaningful.
-- -----------------------------------------------------------------------------
CREATE OR REPLACE VIEW campaign_metrics AS
SELECT
    -- identity columns
    campaign_id,
    campaign_name,
    platform,
    post_type,
    post_date,
    post_time,
    content_theme,
    target_audience,
    boosted_post,

    -- raw spend / volume
    spend_usd,
    reach,
    impressions,
    engagements,
    clicks,
    conversions,
    conversion_value_usd,

    -- passthrough metrics already in the table
    cpc_usd,
    ctr,
    engagement_rate,
    hashtag_count,
    emoji_count,
    word_count,
    sentiment_score,
    video_length_seconds,

    -- ROAS: revenue returned per dollar spent
    -- Formula: conversion_value_usd / spend_usd
    ROUND(
        conversion_value_usd / spend_usd,
        4
    ) AS roas,

    -- Cost per conversion: how much was paid for each conversion
    -- Formula: spend_usd / conversions
    -- Named cost_per_conversion to distinguish from cpc_usd (cost per click)
    ROUND(
        spend_usd / conversions,
        4
    ) AS cost_per_conversion,

    -- Conversion rate: share of clicks that resulted in a conversion
    -- Formula: conversions / clicks
    ROUND(
        conversions::NUMERIC / clicks,
        4
    ) AS conversion_rate,

    -- Efficiency rank: ROAS rank within each platform (1 = highest ROAS)
    -- Ties share the lowest rank number, matching pandas rank(method='min')
    RANK() OVER (
        PARTITION BY platform
        ORDER BY conversion_value_usd / spend_usd DESC
    ) AS efficiency_rank,

    -- Platform mean ROAS: average ROAS across all campaigns on this platform
    -- (per-row average, not weighted by spend — matches AVG(roas) in platform_summary)
    ROUND(
        AVG(conversion_value_usd / spend_usd) OVER (PARTITION BY platform),
        4
    ) AS platform_mean_roas,

    -- Platform ROAS std dev (sample stddev, ddof=1 — matches pandas .std() default)
    -- NULL for platforms with exactly one campaign; handle in application code
    ROUND(
        STDDEV_SAMP(conversion_value_usd / spend_usd) OVER (PARTITION BY platform),
        4
    ) AS platform_stddev_roas    

FROM campaigns
WHERE
    spend_usd   > 0
    AND conversions > 0;


-- -----------------------------------------------------------------------------
-- platform_summary
-- Aggregate rollup by platform — useful for dashboard / summary endpoints.
-- Pulled from campaign_metrics so filters and rounding stay consistent.
-- -----------------------------------------------------------------------------
CREATE OR REPLACE VIEW platform_summary AS
SELECT
    platform,
    COUNT(*)                            AS total_campaigns,
    SUM(spend_usd)                      AS total_spend_usd,
    SUM(conversion_value_usd)           AS total_conversion_value_usd,

    -- Aggregate ROAS: total value / total spend (not an average of per-row ROAS)
    ROUND(
        SUM(conversion_value_usd) / NULLIF(SUM(spend_usd), 0),
        4
    )                                   AS aggregate_roas,

    ROUND(AVG(roas), 4)                 AS avg_roas,
    ROUND(AVG(cost_per_conversion), 4)  AS avg_cost_per_conversion,
    ROUND(AVG(conversion_rate), 4)      AS avg_conversion_rate,
    ROUND(AVG(ctr), 4)                  AS avg_ctr,
    ROUND(AVG(engagement_rate), 4)      AS avg_engagement_rate,
    SUM(impressions)                    AS total_impressions,
    SUM(conversions)                    AS total_conversions

FROM campaign_metrics
GROUP BY platform
ORDER BY aggregate_roas DESC;