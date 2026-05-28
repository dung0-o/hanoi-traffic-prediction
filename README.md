# Hanoi Traffic Congestion Prediction

End-to-end pipeline for predicting traffic congestion in Hanoi using TomTom API, PostgreSQL, XGBoost, and Streamlit.

## Project Overview

This project collects real-time traffic data from TomTom API, stores it in a cloud PostgreSQL database (Supabase), trains an XGBoost model, and provides an interactive Streamlit dashboard for predictions.

## Key Results
| Model	| R² | MAE |
|-------|----|-----|
| XGBoost (with recent history)	| 0.98 | 0.019 |
| XGBoost (without recent history) | 0.75	| 0.094 |

## Model Performance Analysis

### The High R²: Real but Context-Dependent

The XGBoost model achieves R² = 0.98 on the test set. This is not due to data leakage, but it must be interpreted carefully.

**Why the high R² is legitimate:**
- Rolling and lag features use only past observations within the same day
- No future data is ever used in predictions
- Features are all available at prediction time

**Why the high R² is inflated:**

| Metric | Value | Implication |
|--------|-------|-------------|
| Overall congestion variance | 0.123 | Moderate spread across dataset |
| Daily variance (mean) | 0.071 | Low variation within a single day |
| Daily variance < 0.05 | 66.7% of days | Most days have very stable traffic |
| Mean change (30 min) | 0.113 | Typical change is only 11% |
| Median change (30 min) | 0.050 | Half the time, change is less than 5% |

These statistics show that traffic in this dataset is inherently stable. When the target variable barely changes, any model that predicts "no change" will achieve high accuracy. The rolling mean feature (57.5% importance) essentially captures this stability.

**What the 0.98 R² actually means:**
- The model is excellent at predicting next-30-minute congestion when recent history is available
- This is genuinely useful for real-time navigation
- It does NOT mean the model has discovered complex traffic patterns

### The Genuine Prediction Power: R² = 0.75

When rolling and lag features are removed, the model must predict congestion using only:
- Time of day (hour, minute)
- Day of week
- Weather conditions
- Route characteristics (length, straightness)
- Rush hour flags
- Holiday indicators

The resulting R² = 0.75 represents the model's true ability to predict congestion from contextual features alone, without relying on recent traffic history.

### Why No Data Leakage

Rolling and lag features are computed correctly:

```python
df = df.sort_values(['route_id', 'observed_time'])
congestion_by_route_and_date = df.groupby(['route_id', 'date'])['congestion_ratio']

df['congestion_lag_1'] = congestion_by_route_and_date.shift(1)
df['congestion_lag_2'] = congestion_by_route_and_date.shift(2)
df['congestion_rolling_mean_3'] = congestion_by_route_and_date.transform(
    lambda x: x.rolling(3, min_periods=1).mean()
)
df['congestion_rolling_std_3'] = congestion_by_route_and_date.transform(
    lambda x: x.rolling(3, min_periods=1).std().fillna(0)
)

# Drop rows without enough history
df = df.dropna(subset=['congestion_lag_2'])
```
Each day starts fresh. No future data is used. The first two observations of each day are dropped.

### Feature Importance
| Feature | Importance |
|---------|------------|
| Rolling mean (90 min) | 57.5% |
| Lag 1 (30 min ago) | 5.5% |
| Lag 2 (60 min ago) | 5.3% |
| Rolling deviation (90 min) | 4.3% |
| Hour (cos) | 2.8% |

Without recent history, rush hour becomes the most important feature (21%), followed by hour (14%). This confirms that time-based patterns are the primary signal when recent history is unavailable.

#### Why Rolling Mean is the Top Feature (57.5% importance)

The rolling mean of the last 3 observations (90 minutes) is the strongest predictor because:
1. Traffic changes slowly; the average of recent history is highly stable
2. Single lag values (30 min ago) are noisier
3. This confirms that short-term traffic forecasting is primarily a smoothing problem

### What the Model Actually Predicts Well

| Prediction task | R² | Useful for |
|----------------|-----|-------------|
| Next 30 minutes (with recent history) | 0.98 | Real-time traffic apps |
| Long-horizon (without recent history) | 0.75 | Trip planning hours in advance |

### What the Model Does NOT Predict Well

| Limitation | Why |
|------------|-----|
| Sudden accidents | No accident data in training |
| Traffic on new routes | No training data |

### Cost-Benefit Analysis

| Metric | Value |
|--------|-------|
| API cost per day (TomTom) | $0 (free tier: 2,500 requests) |
| Model retraining cost | < 1 minute |
| Inference time per prediction | < 0.01 seconds |
| Database storage (10,000+ rows) | < 15 MB |

The model is cheap enough to run in production for a small to medium user base.

## Frontend Dashboard Showcase

The Streamlit dashboard provides an interactive interface for traffic prediction.

### Dashboard Features
| Feature | Description |
|---------|-------------|
| Route selection | Dropdown menu to select from 40 Hanoi routes |
| Interactive map | Folium map showing route polyline with start/end markers |
| Time inputs | Hour and minute selection (6 AM - 7 PM) |
| Day of week | Monday to Sunday selection |
| Weather inputs | Temperature and weather condition (Clear, Clouds, Rain, etc.) |
| Holiday toggle | Public holiday indicator |
| Real-time prediction | Congestion ratio and level (Light/Moderate/Heavy) |
| Gauge chart | Visual representation of congestion level |
| Travel time estimate | Estimated travel time based on congestion |
| Recommendations | Travel advice based on prediction |

### Dashboard Screenshot
![App Showcase](./app/app_showcase.png)

## Pipeline Architecture
```
TomTom API ──┐
Open-Meteo ──┼──> PostgreSQL ──> XGBoost ──> Streamlit Dashboard
Holidays ────┘
```

## Repository Structure
```
hanoi-traffic-prediction/
├── sql/
│   └── schema.sql                      # Database schema
├── notebooks/
│   ├── 01_data_collection.ipynb        # Collect traffic, weather, holidays
│   └── 02_model_training.ipynb         # Feature engineering + XGBoost + model export
├── app/
│   ├── streamlit_app.py                # Interactive dashboard
│   ├── utils.py                        # Feature engineering helpers
│   └── .streamlit/
│       └── secrets.toml                # Local secrets (gitignored)
├── models/
│   ├── traffic_model.pkl               # Trained XGBoost model
│   ├── feature_columns.pkl             # Column order for inference
│   └── model_metadata.pkl              # Version, R², MAE, params, date range
├── data/
│   └── README.md                       # Data source documentation
├── requirements.txt
├── .gitignore
└── README.md
```

## Database Schema (Supabase PostgreSQL)

| Table | Purpose |
|-------|---------|
| `routes` | Static route information (40 routes) |
| `weather_data` | Hourly weather from Open-Meteo |
| `traffic_observations` | Time-series traffic data |
| `holidays` | Vietnamese public holidays |
| `route_geometries` | Route polylines for map display |

## Setup

### 1. Database Setup

1. Create a free Supabase project
2. Run `sql/schema.sql` in the Supabase SQL Editor
3. Add routes

### 2. Environment Variables

#### For Local Development (Streamlit Secrets)

Create `.streamlit/secrets.toml` in the `app/` directory:

```toml
# app/.streamlit/secrets.toml

SUPABASE_DB_URL = "postgresql://postgres:YOUR_PASSWORD@db.xxxxxxxxxxxx.supabase.co:5432/postgres"
TOMTOM_API_KEY = "your_tomtom_api_key"
```

#### For Google Colab (Data Collection)
Add these secrets to Colab:

| Secret Name | Value |
|-------------|-------|
| `SUPABASE_DB_URL` | PostgreSQL connection string (Session pooler mode) |
| `TOMTOM_API_KEY` | TomTom API key |

### 3. Run Data Collection

Open `notebooks/01_data_collection.ipynb` in Google Colab and run all cells. The notebook:
- Collects traffic data every 30 minutes
- Fetches weather data from Open-Meteo
- Uploads holidays to the database
- Stores route polylines from TomTom

### 4. Train Model

Run `notebooks/02_model_training.ipynb` to:
- Load data from PostgreSQL
- Engineer features (cyclical time, lag, rolling statistics)
- Train XGBoost with Optuna hyperparameter tuning
- Evaluate with time series cross-validation

### 5. Run Dashboard (Local)

```bash
cd app
streamlit run streamlit_app.py
```

## Limitations
- Traffic in this dataset is highly stable (low variance)

- Only 11 days of data (6 AM - 7 PM)

- High autocorrelation inflates R² for short-term predictions

## Technologies
- **Data Collection:** TomTom API, Open-Meteo API, holidays library

- **Database:** PostgreSQL (Supabase cloud)

- **Modelling:** XGBoost, Optuna, scikit-learn

- **Frontend:** Streamlit, Folium

- **Environment:** Google Colab, Python 3.11

## License
The MIT License (MIT)