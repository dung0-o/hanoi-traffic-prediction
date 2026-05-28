import streamlit as st
import pandas as pd
import numpy as np
import folium
import json
import joblib
from pathlib import Path
from streamlit_folium import st_folium
from sqlalchemy import create_engine, text
import plotly.graph_objects as go

st.set_page_config(
    page_title="Hanoi Traffic Predictor",
    page_icon=":vertical_traffic_light:",
    layout="wide",
    initial_sidebar_state="expanded"
)

# ============================================================
# Initialize Session State
# ============================================================

if "selected_route_id" not in st.session_state:
    st.session_state.selected_route_id = None

if "prediction_made" not in st.session_state:
    st.session_state.prediction_made = False

if "last_prediction" not in st.session_state:
    st.session_state.last_prediction = None

# ============================================================
# Load Model and Artifacts
# ============================================================

@st.cache_resource
def load_model():
    model_path = Path(__file__).parent.parent / 'models' / 'traffic_model.pkl'
    features_path = Path(__file__).parent.parent / 'models' / 'feature_columns.pkl'
    metadata_path = Path(__file__).parent.parent / 'models' / 'model_metadata.pkl'

    model = joblib.load(model_path)
    feature_columns = joblib.load(features_path)
    metadata = joblib.load(metadata_path) if metadata_path.exists() else None

    return model, feature_columns, metadata

# ============================================================
# Database Connection
# ============================================================

@st.cache_resource
def init_connection():
    return create_engine(st.secrets["SUPABASE_DB_URL"])

engine = init_connection()
model, feature_columns, metadata = load_model()

# ============================================================
# Load Data (cached)
# ============================================================

@st.cache_data(ttl=3600)
def load_routes():
    query = """
    SELECT 
        r.route_id,
        r.route_name,
        r.start_lat,
        r.start_lon,
        r.end_lat,
        r.end_lon,
        rg.length_meters,
        rg.straightness_ratio
    FROM routes r
    LEFT JOIN route_geometries rg ON r.route_id = rg.route_id
    ORDER BY r.route_id
    """
    return pd.read_sql(query, engine)

@st.cache_data(ttl=3600)
def load_route_geometry(route_id):
    query = text("""
    SELECT polyline_geojson 
    FROM route_geometries 
    WHERE route_id = :route_id
    """)
    with engine.connect() as conn:
        result = conn.execute(query, {'route_id': route_id}).fetchone()

    if result and result[0]:
        if isinstance(result[0], dict):
            return result[0]
        elif isinstance(result[0], str):
            return json.loads(result[0])
    return None

routes_df = load_routes()
route_names = dict(zip(routes_df['route_id'], routes_df['route_name']))

# ============================================================
# Feature Engineering Function
# ============================================================

def engineer_features(route_id, hour, minute, day_of_week, temperature,
                      weather_condition, is_holiday, is_rush_hour,
                      length_meters, straightness_ratio):

    hour_sin = np.sin(2 * np.pi * hour / 24)
    hour_cos = np.cos(2 * np.pi * hour / 24)
    minute_sin = np.sin(2 * np.pi * minute / 60)
    minute_cos = np.cos(2 * np.pi * minute / 60)
    dow_sin = np.sin(2 * np.pi * day_of_week / 7)
    dow_cos = np.cos(2 * np.pi * day_of_week / 7)

    minutes_elapsed = (hour - 6) * 60 + minute
    minutes_elapsed = max(0, min(minutes_elapsed, 780))

    rush_hour_route = float(is_rush_hour * route_id)
    hour_sin_length = float(hour_sin * length_meters)
    hour_sin_dow = float(hour_sin * dow_sin)
    hour_cos_dow = float(hour_cos * dow_sin)

    weather_map = {'Clear': 0, 'Clouds': 1, 'Rain': 2, 'Fog': 3, 'Thunderstorm': 4}
    weather_encoded = float(weather_map.get(weather_condition, 1))

    features = {
        'hour_sin': float(hour_sin),
        'hour_cos': float(hour_cos),
        'minute_sin': float(minute_sin),
        'minute_cos': float(minute_cos),
        'dow_sin': float(dow_sin),
        'dow_cos': float(dow_cos),
        'minutes_elapsed': float(minutes_elapsed),
        'is_rush_hour': float(is_rush_hour),
        'weather_encoded': weather_encoded,
        'temperature_celsius': float(temperature),
        'length_meters': float(length_meters),
        'straightness_ratio': float(straightness_ratio),
        'rush_hour_route': rush_hour_route,
        'hour_sin_length': hour_sin_length,
        'hour_sin_dow': hour_sin_dow,
        'hour_cos_dow': hour_cos_dow,
        'is_holiday': float(is_holiday)
    }

    df_features = pd.DataFrame([features])
    df_features = df_features.astype(np.float32)

    return df_features

def get_congestion_level(ratio):
    if ratio < 1.3:
        return ("Light", "#00FF00")
    elif ratio < 2.0:
        return ("Moderate", "#FFA500")
    else:
        return ("Heavy", "#FF0000")

def create_route_map(route_id, route_geojson):
    route = routes_df[routes_df['route_id'] == route_id].iloc[0]
    center_lat = (route['start_lat'] + route['end_lat']) / 2
    center_lon = (route['start_lon'] + route['end_lon']) / 2

    m = folium.Map(location=[center_lat, center_lon], zoom_start=13, control_scale=True)

    if route_geojson:
        folium.GeoJson(
            route_geojson,
            style_function=lambda x: {'color': '#00FFFF', 'weight': 5, 'opacity': 0.8},
            tooltip=route['route_name']
        ).add_to(m)

    folium.Marker(
        [route['start_lat'], route['start_lon']],
        popup="Start",
        icon=folium.Icon(color='green', icon='play', prefix='fa')
    ).add_to(m)

    folium.Marker(
        [route['end_lat'], route['end_lon']],
        popup="End",
        icon=folium.Icon(color='red', icon='stop', prefix='fa')
    ).add_to(m)

    return m

# ============================================================
# Sidebar
# ============================================================

st.sidebar.title("Traffic Predictor")
st.sidebar.markdown("---")

selected_route_id = st.sidebar.selectbox(
    "Select Route",
    options=routes_df['route_id'].tolist(),
    format_func=lambda x: route_names.get(x, f"Route {x}"),
    key="route_selector"
)

if selected_route_id != st.session_state.selected_route_id:
    st.session_state.selected_route_id = selected_route_id
    st.session_state.prediction_made = False

col1, col2 = st.sidebar.columns(2)
with col1:
    hour = st.number_input("Hour (0-23)", min_value=0, max_value=23, value=8)
with col2:
    minute = st.selectbox("Minute", [0, 30], index=0)

day_of_week = st.sidebar.selectbox(
    "Day of Week",
    options=["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"],
    index=1
)
day_map = {"Monday": 0, "Tuesday": 1, "Wednesday": 2, "Thursday": 3, "Friday": 4, "Saturday": 5, "Sunday": 6}
day_of_week_num = day_map[day_of_week]
is_weekend = 1 if day_of_week in ["Saturday", "Sunday"] else 0
is_rush_hour = 1 if (7 <= hour <= 9) or (17 <= hour <= 19) else 0

st.sidebar.markdown("---")
st.sidebar.subheader("Weather Conditions")
temperature = st.sidebar.slider("Temperature (°C)", 15, 40, 28)
weather_condition = st.sidebar.selectbox(
    "Weather",
    options=["Clear", "Clouds", "Rain", "Fog", "Thunderstorm"],
    index=0
)
is_holiday = st.sidebar.checkbox("Is Public Holiday", value=False)

st.sidebar.markdown("---")
predict_button = st.sidebar.button("Predict Congestion", type="primary", use_container_width=True)

# ============================================================
# Main Content
# ============================================================

st.title("Hanoi Traffic Congestion Predictor")
st.markdown("Predict traffic congestion for major routes in Hanoi based on time, weather, and route characteristics.")

current_route_id = st.session_state.selected_route_id
if current_route_id is None:
    current_route_id = routes_df['route_id'].iloc[0]
    st.session_state.selected_route_id = current_route_id

route_info = routes_df[routes_df['route_id'] == current_route_id].iloc[0]
route_geojson = load_route_geometry(current_route_id)

st.subheader(f"Route: {route_info['route_name']}")
col_map, col_stats = st.columns([2, 1])

with col_map:
    if route_geojson:
        m = create_route_map(current_route_id, route_geojson)
        st_folium(m, width=700, height=400, key="traffic_map")
    else:
        st.warning("Route geometry not available")

with col_stats:
    st.metric("Distance", f"{route_info['length_meters'] / 1000:.1f} km")
    st.metric("Straightness Ratio", f"{route_info['straightness_ratio']:.2f}")
    st.caption("1.0 = perfectly straight")

# ============================================================
# Prediction (only runs when button is clicked)
# ============================================================

if predict_button:
    with st.spinner("Predicting congestion..."):
        try:
            features_df = engineer_features(
                route_id=current_route_id,
                hour=hour,
                minute=minute,
                day_of_week=day_of_week_num,
                temperature=temperature,
                weather_condition=weather_condition,
                is_holiday=is_holiday,
                is_rush_hour=is_rush_hour,
                length_meters=route_info['length_meters'],
                straightness_ratio=route_info['straightness_ratio']
            )

            features_df = features_df[feature_columns]
            congestion_ratio = model.predict(features_df)[0]
            level_text, level_color = get_congestion_level(congestion_ratio)

            # Store prediction in session state
            st.session_state.last_prediction = {
                'ratio': congestion_ratio,
                'level': level_text,
                'color': level_color,
                'route_id': current_route_id,
                'hour': hour,
                'minute': minute
            }
            st.session_state.prediction_made = True

        except Exception as e:
            st.error(f"Prediction failed: {e}")

if st.session_state.prediction_made and st.session_state.last_prediction:
    pred = st.session_state.last_prediction

    if (pred['route_id'] == current_route_id and 
        pred['hour'] == hour and 
        pred['minute'] == minute):
        
        st.markdown("---")
        st.subheader("Prediction Result")
        
        col1, col2, col3 = st.columns(3)
        
        with col1:
            st.metric("Congestion Ratio", f"{pred['ratio']:.2f}", help="1.0 = free flow, >2.0 = heavy")
        
        with col2:
            st.markdown(
                f"""
                <div style="background-color:{pred['color']}20; padding:1rem; border-radius:10px; text-align:center">
                    <h3 style="margin:0; color:{pred['color']}">{pred['level']}</h3>
                    <p style="margin:0; font-size:0.8rem">Expected Condition</p>
                </div>
                """,
                unsafe_allow_html=True
            )
        
        with col3:
            free_flow_min = (route_info['length_meters'] / 1000) / 30 * 60
            estimated_min = free_flow_min * pred['ratio']
            st.metric(
                "Estimated Travel Time",
                f"{estimated_min:.0f} min",
                delta=f"{estimated_min - free_flow_min:.0f} min",
                delta_color="inverse")

        fig = go.Figure(go.Indicator(
            mode="gauge+number+delta",
            value=pred['ratio'],
            title={"text": "Congestion Ratio"},
            domain={'x': [0, 1], 'y': [0, 1]},
            gauge={
                'axis': {'range': [0, 3.0], 'tickwidth': 1},
                'bar': {'color': 'rgba(0,0,0,0)'},
                'steps': [
                    {'range': [0, 1.3], 'color': 'green'},
                    {'range': [1.3, 2.0], 'color': 'orange'},
                    {'range': [2.0, 3.0], 'color': 'red'}
                ],
                'threshold': {
                    'line': {'color': "cyan", 'width': 4},
                    'thickness': 1,
                    'value': pred['ratio']
                }
            }
        ))
        fig.update_layout(height=300)
        st.plotly_chart(fig, use_container_width=True)

        st.markdown("---")
        st.subheader("Recommendation")
        
        if pred['ratio'] > 2.0:
            st.warning("Heavy congestion expected. Consider leaving 20-30 minutes earlier or taking an alternative route.")
        elif pred['ratio'] > 1.3:
            st.info("Moderate congestion expected. Allow extra 10-15 minutes for your trip.")
        else:
            st.success("Light traffic expected. Normal travel time.")

# ============================================================
# Footer
# ============================================================

st.markdown("---")
st.caption("Data source: TomTom Routing API | Weather: Open-Meteo | Predictions based on XGBoost model trained on 11 days of Hanoi traffic data")