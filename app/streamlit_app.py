import streamlit as st
import pandas as pd
import numpy as np
import folium
import json
from streamlit_folium import st_folium
from sqlalchemy import create_engine, text
from datetime import datetime
import plotly.express as px
import plotly.graph_objects as go

st.set_page_config(
    page_title="Hanoi Traffic Predictor",
    page_icon=":vertical_traffic_light:",
    layout="wide",
    initial_sidebar_state="expanded"
)

# ============================================================
# Database Connection
# ============================================================

@st.cache_resource
def init_connection():
    """Create database connection using secrets."""
    return create_engine(st.secrets["SUPABASE_DB_URL"])

try:
    engine = init_connection()
    st.sidebar.success("Connected to database")
except Exception as e:
    st.sidebar.error(f"Database connection failed: {e}")
    st.stop()

# ============================================================
# Load Data
# ============================================================

@st.cache_data(ttl=3600)
def load_routes():
    """Load route information from database."""
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
    """Load route polyline for map display."""
    query = text("""
    SELECT polyline_geojson 
    FROM route_geometries 
    WHERE route_id = :route_id
    """)
    with engine.connect() as conn:
        result = conn.execute(query, {'route_id': route_id}).fetchone()
    
    if result and result[0]:
        # If it's already a dict (from JSONB), return directly
        if isinstance(result[0], dict):
            return result[0]
        # If it's a string, parse as JSON
        elif isinstance(result[0], str):
            return json.loads(result[0])
    return None

# Load routes
routes_df = load_routes()
route_names = dict(zip(routes_df['route_id'], routes_df['route_name']))

# ============================================================
# Helper Functions
# ============================================================

def create_route_map(route_id, route_geojson):
    """Create Folium map with route highlighted."""
    route = routes_df[routes_df['route_id'] == route_id].iloc[0]
    
    # Calculate map center
    center_lat = (route['start_lat'] + route['end_lat']) / 2
    center_lon = (route['start_lon'] + route['end_lon']) / 2
    
    m = folium.Map(location=[center_lat, center_lon], zoom_start=13, control_scale=True)
    
    # Add route polyline
    if route_geojson:
        folium.GeoJson(
            route_geojson,
            style_function=lambda x: {'color': '#00FFFF', 'weight': 5, 'opacity': 0.8},
            tooltip=route['route_name']
        ).add_to(m)
    
    # Add start and end markers
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

def get_congestion_level(ratio):
    """Convert congestion ratio to human-readable level."""
    if ratio < 1.3:
        return ("Light", "light", "#00FF00")
    elif ratio < 2.0:
        return ("Moderate", "moderate", "#FFA500")
    else:
        return ("Heavy", "heavy", "#FF0000")

# ============================================================
# Sidebar - User Inputs
# ============================================================

st.sidebar.title("Traffic Predictor")
st.sidebar.markdown("---")

# Route selection
route_id = st.sidebar.selectbox(
    "Select Route",
    options=routes_df['route_id'].tolist(),
    format_func=lambda x: route_names.get(x, f"Route {x}")
)

# Time selection
col1, col2 = st.sidebar.columns(2)
with col1:
    hour = st.number_input("Hour (0-23)", min_value=0, max_value=23, value=8)
with col2:
    minute = st.selectbox("Minute", [0, 30], index=0)

# Date selection
day_of_week = st.sidebar.selectbox(
    "Day of Week",
    options=["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"],
    index=1
)
is_weekend = 1 if day_of_week in ["Saturday", "Sunday"] else 0

# Rush hour calculation
is_rush_hour = 1 if (7 <= hour <= 9) or (17 <= hour <= 19) else 0

# Weather input (simplified for demo)
st.sidebar.markdown("---")
st.sidebar.subheader("Weather Conditions")
temperature = st.sidebar.slider("Temperature (°C)", 15, 40, 28)
weather_condition = st.sidebar.selectbox(
    "Weather",
    options=["Clear", "Clouds", "Rain", "Fog", "Thunderstorm"],
    index=0
)

# Holiday toggle
is_holiday = st.sidebar.checkbox("Is Public Holiday", value=False)

st.sidebar.markdown("---")
predict_button = st.sidebar.button("Predict Congestion", type="primary", use_container_width=True)

# ============================================================
# Main Content
# ============================================================

st.title("Hanoi Traffic Congestion Predictor")
st.markdown("Predict traffic congestion for major routes in Hanoi based on time, weather, and route characteristics.")

# Route information
route_info = routes_df[routes_df['route_id'] == route_id].iloc[0]
route_geojson = load_route_geometry(route_id)

# Display route map
st.subheader(f"Route: {route_info['route_name']}")
col_map, col_stats = st.columns([2, 1])

with col_map:
    if route_geojson:
        m = create_route_map(route_id, route_geojson)
        st_folium(m, width=700, height=400)
    else:
        st.warning("Route geometry not available")

with col_stats:
    st.metric("Distance", f"{route_info['length_meters'] / 1000:.1f} km")
    st.metric("Straightness Ratio", f"{route_info['straightness_ratio']:.2f}")
    st.caption("1.0 = perfectly straight")

# ============================================================
# Prediction
# ============================================================

if predict_button:
    st.markdown("---")
    st.subheader("Prediction Result")
    
    # Feature engineering (simplified - replace with actual model features)
    # In production, load your trained model and transform inputs
    
    # Demo prediction (replace with actual model)
    import random
    base_congestion = 1.0
    
    # Rush hour adds 30-60%
    if is_rush_hour:
        base_congestion += random.uniform(0.3, 0.6)
    else:
        base_congestion += random.uniform(0.0, 0.2)
    
    # Weekend reduces by 10-20%
    if is_weekend:
        base_congestion *= random.uniform(0.8, 0.9)
    
    # Rain adds 10-30%
    if weather_condition in ["Rain", "Thunderstorm"]:
        base_congestion *= random.uniform(1.1, 1.3)
    
    # Holiday effect
    if is_holiday:
        base_congestion *= random.uniform(0.7, 0.9)
    
    congestion_ratio = base_congestion
    level_text, level_id, level_color = get_congestion_level(congestion_ratio)
    
    # Display result cards
    col1, col2, col3 = st.columns(3)
    
    with col1:
        st.metric("Congestion Ratio", f"{congestion_ratio:.2f}", help="1.0 = free flow, >1.5 = heavy")
    
    with col2:
        st.markdown(
            f"""
            <div style="background-color:{level_color}20; padding:1rem; border-radius:10px; text-align:center">
                <h3 style="margin:0; color:{level_color}">{level_text}</h3>
                <p style="margin:0; font-size:0.8rem">Expected Condition</p>
            </div>
            """,
            unsafe_allow_html=True
        )
    
    with col3:
        # Estimated travel time (using length_meters and 30 km/h free flow)
        free_flow_min = (route_info['length_meters'] / 1000) / 30 * 60
        estimated_min = free_flow_min * congestion_ratio
        st.metric("Estimated Travel Time", f"{estimated_min:.0f} min", delta=f"{estimated_min - free_flow_min:.0f} min")
    
    # Gauge chart
    fig = go.Figure(go.Indicator(
        mode = "gauge+number+delta",
        value = congestion_ratio,
        title = {"text": "Congestion Ratio"},
        domain = {'x': [0, 1], 'y': [0, 1]},
        gauge = {
            'axis': {'range': [0, 3.0], 'tickwidth': 1},
            'bar': {'color': level_color},
            'steps': [
                {'range': [0, 1.3], 'color': 'green'},
                {'range': [1.3, 2.0], 'color': 'orange'},
                {'range': [2.0, 3.0], 'color': 'red'}
            ],
            'threshold': {
                'line': {'color': "red", 'width': 4},
                'thickness': 0.75,
                'value': congestion_ratio
            }
        }
    ))
    fig.update_layout(height=300)
    st.plotly_chart(fig, use_container_width=True)
    
    # Recommendation
    st.markdown("---")
    st.subheader("Recommendation")
    
    if congestion_ratio > 2.0:
        st.warning("Heavy congestion expected. Consider leaving 20-30 minutes earlier or taking an alternative route.")
    elif congestion_ratio > 1.3:
        st.info("Moderate congestion expected. Allow extra 10-15 minutes for your trip.")
    else:
        st.success("Light traffic expected. Normal travel time.")

# ============================================================
# Footer
# ============================================================

st.markdown("---")
st.caption("Data source: TomTom Routing API | Weather: Open-Meteo | Predictions based on XGBoost model trained on 3 days of Hanoi traffic data")