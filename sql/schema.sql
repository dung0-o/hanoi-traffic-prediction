-- ============================================================
-- HANOI TRAFFIC PREDICTION DATABASE SCHEMA
-- ============================================================

-- Table 1: routes (static route information)
CREATE TABLE IF NOT EXISTS routes (
    route_id SERIAL PRIMARY KEY,
    route_name VARCHAR(100) NOT NULL UNIQUE,
    start_lat DECIMAL(10,6) NOT NULL,
    start_lon DECIMAL(10,6) NOT NULL,
    end_lat DECIMAL(10,6) NOT NULL,
    end_lon DECIMAL(10,6) NOT NULL,
    length_meters INTEGER,
    free_flow_time_seconds INTEGER,
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_routes_name ON routes(route_name);

-- Table 2: weather_data (hourly weather observations)
CREATE TABLE IF NOT EXISTS weather_data (
    weather_id SERIAL PRIMARY KEY,
    observation_date DATE NOT NULL,
    hour INTEGER NOT NULL CHECK (hour >= 0 AND hour <= 23),
    temperature_celsius DECIMAL(4,2),
    humidity_percent INTEGER,
    precipitation_mm DECIMAL(4,2),
    rain_mm DECIMAL(4,2),
    weather_code INTEGER,
    weather_condition VARCHAR(50),
    source VARCHAR(50) DEFAULT 'Open-Meteo',
    created_at TIMESTAMP DEFAULT NOW(),
    UNIQUE(observation_date, hour)
);

CREATE INDEX IF NOT EXISTS idx_weather_date_hour ON weather_data(observation_date, hour);

-- Table 3: traffic_observations (time-series data)
CREATE TABLE IF NOT EXISTS traffic_observations (
    observation_id BIGSERIAL PRIMARY KEY,
    route_id INTEGER NOT NULL REFERENCES routes(route_id) ON DELETE CASCADE,
    observed_time TIMESTAMP NOT NULL,
    travel_time_seconds INTEGER NOT NULL,
    no_traffic_time_seconds INTEGER NOT NULL,
    congestion_ratio DECIMAL(4,2) GENERATED ALWAYS AS 
        (travel_time_seconds::DECIMAL / NULLIF(no_traffic_time_seconds, 0)) STORED,
    hour INTEGER GENERATED ALWAYS AS (EXTRACT(HOUR FROM observed_time)) STORED,
    minute INTEGER GENERATED ALWAYS AS (EXTRACT(MINUTE FROM observed_time)) STORED,
    day_of_week INTEGER GENERATED ALWAYS AS (EXTRACT(DOW FROM observed_time)) STORED,
    is_weekend BOOLEAN GENERATED ALWAYS AS (EXTRACT(DOW FROM observed_time) IN (0, 6)) STORED,
    is_rush_hour BOOLEAN GENERATED ALWAYS AS 
        ((EXTRACT(HOUR FROM observed_time) BETWEEN 7 AND 9) OR 
         (EXTRACT(HOUR FROM observed_time) BETWEEN 17 AND 19)) STORED,
    created_at TIMESTAMP DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_traffic_route_time ON traffic_observations(route_id, observed_time);
CREATE INDEX IF NOT EXISTS idx_traffic_route ON traffic_observations(route_id);
CREATE INDEX IF NOT EXISTS idx_traffic_time ON traffic_observations(observed_time);

-- Table 4: holidays
CREATE TABLE IF NOT EXISTS holidays (
    holiday_id SERIAL PRIMARY KEY,
    holiday_date DATE NOT NULL UNIQUE,
    holiday_name VARCHAR(100) NOT NULL,
    created_at TIMESTAMP DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_holidays_date ON holidays(holiday_date);

-- Table 5: route_geometries (route polylines for map display)
CREATE TABLE IF NOT EXISTS route_geometries (
    geometry_id SERIAL PRIMARY KEY,
    route_id INTEGER NOT NULL REFERENCES routes(route_id) ON DELETE CASCADE,
    polyline_geojson JSONB NOT NULL,
    length_meters INTEGER NOT NULL,
    straightness_ratio DECIMAL(4,3),
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW(),
    UNIQUE(route_id)
);

CREATE INDEX IF NOT EXISTS idx_route_geometries_route ON route_geometries(route_id);

-- ============================================================
-- AUTO-UPDATE TIMESTAMP FUNCTION
-- ============================================================

CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- Apply to routes table
DROP TRIGGER IF EXISTS update_routes_updated_at ON routes;
CREATE TRIGGER update_routes_updated_at
    BEFORE UPDATE ON routes
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at_column();

-- Apply to route_geometries table
DROP TRIGGER IF EXISTS update_route_geometries_updated_at ON route_geometries;
CREATE TRIGGER update_route_geometries_updated_at
    BEFORE UPDATE ON route_geometries
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at_column();

-- ============================================================
-- VERIFICATION QUERIES
-- ============================================================

-- Check all tables created
SELECT table_name FROM information_schema.tables 
WHERE table_schema = 'public' 
ORDER BY table_name;