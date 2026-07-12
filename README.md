# campaign-analysis-2

Social Media Campaign Performance analysis using a synthetic dataset from [Real World Fake Data](https://sonsofhierarchies.com/2025/08/01/rwfd-season-4-dataset-1-social-media-campaign-performance/). This is part 2 of a 3 part series - Pipeline API

A Dockerized data pipeline that ingests social media campaign analytics from CSV into PostgreSQL, computes ROAS-based performance metrics via SQL views, and exposes everything through a FastAPI service — underperformer alerts and platform-level rollups included.

NOTE: As of writing, Real World Fake Data datasets are being migrated [here](https://github.com/MBradbourne/real-world-fake-data).

---

## What it does

- **Ingests** the campaign data csv into Postgres on startup (`init_db.py`)
- **Derives metrics in SQL** (`views.sql`): ROAS, cost per conversion, conversion rate, and a per-platform ROAS percentile rank
- **Flags underperforming campaigns** using percentile rank rather than mean/std — robust to the heavy right-skew in this dataset (see [Design Notes](#design-notes) below)
- **Serves it all via FastAPI**, fully containerized alongside the database

---

## Tech Stack

| Layer | Tool |
|---|---|
| Language | Python 3.12 |
| Package manager | [uv](https://github.com/astral-sh/uv) |
| Ingest | pandas + SQLAlchemy |
| API | FastAPI + SQLAlchemy |
| Database | PostgreSQL 16 (Docker) |
| Orchestration | Docker Compose |

---

## Project Structure

```
campaign-analysis-2/
├── docker-compose.yml
<!--├── .env.example           # copy to .env before running  -->
├── pyproject.toml         # uv-managed, root level (ingest deps only)
├── uv.lock
├── init_db.py             # loads CSV into Postgres, then runs create_views.sql
├── create_views.sql              # campaign_metrics + platform_summary views
├── data/
│   └── synthetic_social_media_campaign_data.csv      # see "Getting the data" below
└── api/
    ├── Dockerfile
    ├── pyproject.toml     # standalone uv project (not a workspace member of root)
    ├── uv.lock
    ├── main.py             # FastAPI app: /health, /alerts, /summary
    └── detection.py        # underperformer detection logic
```

---

## Getting the Data

The dataset's original source link is currently broken. The CSV is included directly in this repository at `data/synthetic_social_media_campaign_data.csv` — cloning the repo is all you need; no separate download step required.

## Quickstart

**Requirements:** Docker and Docker Compose installed. Nothing else — Python and uv run inside the containers.

```bash
git clone <this-repo-url>
cd campaign-analysis-2
cp .env.example .env
docker compose up --build
```

That's it. Once the containers are up:

- API: [http://localhost:8000](http://localhost:8000)
- Interactive docs (Swagger UI): [http://localhost:8000/docs](http://localhost:8000/docs)
- Health check: [http://localhost:8000/health](http://localhost:8000/health)

The `db` service starts first, `ingest` loads the CSV and builds the SQL views, then `api` comes up once ingest succeeds.

---

## API Endpoints

### `GET /health`
Returns API and database connectivity status.

### `GET /alerts`
Flags underperforming campaigns using bottom-X% ROAS rank, computed per platform.

| Query param | Type | Default | Description |
|---|---|---|---|
| `platform` | enum | none | Filter to one platform |
| `bottom_pct` | float (0–1) | `0.02` | Fraction of lowest-ROAS campaigns per platform to flag |

```bash
curl "http://localhost:8000/alerts?bottom_pct=0.05"
```

### `GET /summary`
Platform-level rollup: total spend, total conversion value, aggregate ROAS, and per-metric averages, sourced from the `platform_summary` SQL view.

| Query param | Type | Default | Description |
|---|---|---|---|
| `platform` | enum | none | Filter to one platform |

```bash
curl "http://localhost:8000/summary"
```

Both `platform` filters use a dropdown-enabled enum built dynamically from the distinct platform values in the database, so `/docs` renders it as a proper selector and invalid values 422 automatically.

---

## Runbook

### Full rebuild (needed after any `views.sql` change)

The `-v` flag is essential — it wipes the Postgres data volume so schema/view changes actually take effect on re-ingest.

```bash
docker compose down -v
docker compose up --build
```

### Rebuild/restart just the API

Use this when `db` and `ingest` have already succeeded and you don't want to re-run ingest.

```bash
docker compose up --build --no-deps api
```

### Access the database directly

```bash
docker compose exec db psql -U analyticsuser -d analyticsdb
```

Or a one-off query:

```bash
docker compose exec db psql -U analyticsuser -d analyticsdb -c "SELECT * FROM platform_summary;"
```

### Remove a stopped/errored container without touching others

```bash
docker compose rm -f ingest
```

### Sweep-test alert thresholds

```bash
for t in 0.01 0.02 0.05 0.1; do
  echo "bottom_pct=$t:"
  curl -s "http://localhost:8000/alerts?bottom_pct=$t" | python3 -c "import sys,json; print(json.load(sys.stdin)['total_alerts'])"
done
```

### Running the API outside Docker (local dev)

Use `.env.local` for a localhost `DATABASE_URL` (pointed at the Dockerized `db` service exposed on your host):

```bash
cd api
uv sync
uv run fastapi dev main.py
```

---

## Design Notes

**Why percentile rank instead of mean ± std deviation for outlier detection?**

The mean/std approach was tried first and abandoned — it's fundamentally broken on data with heavy right-skew, which this dataset has. On the Instagram platform, for example, `mean_roas ≈ 1196` while `std_roas ≈ 8277`: the standard deviation is roughly 7x the mean, a signature of a few extreme high-ROAS campaigns dragging the spread way up. `mean − 1.0 × std` computed to a negative number, meaning no campaign could ever be flagged — ROAS can't go negative. At very low thresholds the logic degraded into "flag anything below the mean," about half of all campaigns, which isn't a useful signal either.

The current approach uses `PERCENT_RANK()` per platform in `views.sql` — bottom X% of ROAS, rank-based rather than magnitude-based, so it's robust to skew and outliers. Default threshold flags the bottom 2%.

**Known limitation:** `PERCENT_RANK()` always returns 0 for the single lowest-ROAS row on any platform, so a platform with very few campaigns (e.g. n=1) will always have that campaign "in the bottom 0%" and get flagged regardless of `bottom_pct`. A minimum-campaign-count guard for small platforms would fix this — not yet implemented. Worth watching if `/alerts` results look noisy for low-volume platforms.

**Why `SUM(conversion_value_usd) / SUM(spend_usd)` for `aggregate_roas` instead of averaging per-row ROAS?**

Averaging per-campaign ROAS ratios directly is misleading: a platform with one huge-spend/low-ROAS campaign and many tiny-spend/high-ROAS campaigns would look artificially strong under a naive mean. `aggregate_roas` in `platform_summary` is computed as true spend-weighted ROAS instead; `avg_roas` (the naive per-row mean) is also exposed separately for comparison.

**Postgres quirk:** `ROUND(double precision, integer)` doesn't exist in Postgres — the precision-argument overload of `ROUND()` only accepts `numeric`. Any window function returning `double precision` (e.g. `PERCENT_RANK()`) needs an explicit cast: `ROUND(expr::numeric, 4)`.

---

## Known Limitations / Possible Next Steps

- No minimum-campaign-count guard on `/alerts` for low-volume platforms (see above)
- Root `pyproject.toml` includes `fastapi[standard]` as a dependency even though the ingest script never imports it — unused weight in the ingest container, flagged for cleanup
- `api/` and the project root are two independent uv projects rather than a uv workspace, by necessity (see `pyproject.toml` comments for the `[tool.uv.workspace]` exclude) — worth knowing if you extend the project and expect workspace-style dependency sharing to just work
