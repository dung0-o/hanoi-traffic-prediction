# Data

Data is stored in Supabase cloud database. Not included in this repository.

## Data Sources

| Data type | Source | Method |
|-----------|--------|--------|
| Traffic | TomTom Routing API | 30-min intervals, 40 routes |
| Weather | Open-Meteo API | Hourly for collection period |
| Holidays | Python holidays library | Vietnamese public holidays 2026 |

## Tables

| Table | Rows | Description |
|-------|------|-------------|
| routes | 40 | Static route coordinates and metadata |
| traffic_observations | 3,300 | Time-series congestion data (3 days) |
| weather_data | 96 | Hourly weather for 4 days |
| holidays | 12 | Vietnamese public holidays 2026 |
| route_geometries | 40 | Route polylines for map display |

## Data Collection Period

| Parameter | Value |
|-----------|-------|
| Start date | 2026-05-17 |
| End date | 2026-05-20 |
| Collection hours | 6:00 AM - 7:00 PM |
| Collection frequency | Every 30 minutes |
| Number of routes | 40 |

## Reproduction

To recreate the dataset, run `notebooks/01_data_collection.ipynb` in Google Colab with:
- TomTom API key (free tier: 2,500 requests/day)
- Supabase connection string (Session pooler mode)

## Data Not Included

The following are NOT committed to this repository:
- Raw CSV files (too large)
- Model pickle files (can be retrained)
- API keys and database credentials

## Schema

See `sql/schema.sql` for complete database schema definition.