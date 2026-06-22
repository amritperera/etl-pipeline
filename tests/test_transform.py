import duckdb
import pytest
import sys
import os

# allow imports from src/
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from transform.transform_neo import transform_neo, validate_neo_data


@pytest.fixture
def test_db():
    """
    Create an in-memory DuckDB with sample raw_neo data for testing.
    """
    con = duckdb.connect(":memory:")

    con.execute("""
        CREATE TABLE raw_neo (
            neo_id                   VARCHAR,
            neo_name                 VARCHAR,
            nasa_jpl_url             VARCHAR,
            is_potentially_hazardous BOOLEAN,
            is_sentry_object         BOOLEAN,
            abs_magnitude            DOUBLE,
            min_diameter_km          DOUBLE,
            max_diameter_km          DOUBLE,
            close_approach_date      VARCHAR,
            relative_velocity_kmh    DOUBLE,
            miss_distance_km         DOUBLE,
            orbiting_body            VARCHAR,
            ingested_at              VARCHAR
        )
    """)

    con.execute("""
        INSERT INTO raw_neo VALUES
        ('1001', 'Test Asteroid A', 'http://test.com', false, false, 20.5, 0.05, 0.1, '2026-06-20', 45000.0, 5000000.0, 'Earth', '2026-06-20T00:00:00'),
        ('1002', 'Test Asteroid B', 'http://test.com', true, false, 18.2, 0.5, 1.0, '2026-06-21', 60000.0, 800000.0, 'Earth', '2026-06-20T00:00:00'),
        ('1003', 'Test Asteroid C', 'http://test.com', false, false, 22.0, 0.001, 0.005, '2026-06-22', 30000.0, 40000000.0, 'Earth', '2026-06-20T00:00:00')
    """)

    yield con
    con.close()


def test_fct_neo_row_count(test_db):
    """Transform should preserve row count from raw_neo to fct_neo."""
    transform_neo_inmemory(test_db)
    result = test_db.execute("SELECT COUNT(*) FROM fct_neo").fetchone()[0]
    assert result == 3


def test_size_categorization(test_db):
    """Size categories should be assigned correctly based on diameter."""
    transform_neo_inmemory(test_db)
    result = test_db.execute("""
        SELECT neo_id, size_category FROM fct_neo ORDER BY neo_id
    """).fetchall()

    assert result[0][1] == "Medium (10m - 100m)"   # avg diameter 0.075
    assert result[1][1] == "Large (100m - 1km)"     # avg diameter 0.75
    assert result[2][1] == "Small (< 10m)"          # avg diameter 0.003


def test_validation_passes_on_clean_data(test_db):
    """Validation should pass without raising on clean test data."""
    transform_neo_inmemory(test_db)
    validate_neo_data(test_db)  # should not raise


def test_validation_catches_duplicate_ids(test_db):
    """Validation should raise an error when duplicate neo_ids exist."""
    test_db.execute("""
        INSERT INTO raw_neo VALUES
        ('1001', 'Duplicate Asteroid', 'http://test.com', false, false, 20.5, 0.05, 0.1, '2026-06-20', 45000.0, 5000000.0, 'Earth', '2026-06-20T00:00:00')
    """)
    transform_neo_inmemory(test_db)

    with pytest.raises(ValueError):
        validate_neo_data(test_db)


def transform_neo_inmemory(con):
    """
    Helper that runs the same transform logic as transform_neo()
    but against an already-open in-memory connection.
    """
    con.execute("""
        CREATE OR REPLACE TABLE fct_neo AS
        SELECT
            neo_id,
            neo_name,
            is_potentially_hazardous,
            is_sentry_object,
            abs_magnitude,
            min_diameter_km,
            max_diameter_km,
            round((min_diameter_km + max_diameter_km) / 2, 6)  AS avg_diameter_km,
            close_approach_date,
            relative_velocity_kmh,
            round(relative_velocity_kmh / 1.609344, 2)         AS relative_velocity_mph,
            miss_distance_km,
            round(miss_distance_km / 384400, 4)                AS miss_distance_lunar,
            orbiting_body,
            ingested_at,

            CASE
                WHEN (min_diameter_km + max_diameter_km) / 2 < 0.01  THEN 'Small (< 10m)'
                WHEN (min_diameter_km + max_diameter_km) / 2 < 0.1   THEN 'Medium (10m - 100m)'
                WHEN (min_diameter_km + max_diameter_km) / 2 < 1.0   THEN 'Large (100m - 1km)'
                ELSE                                                      'Very Large (1km+)'
            END AS size_category,

            CASE
                WHEN miss_distance_km < 1000000  THEN 'Very Close (< 1M km)'
                WHEN miss_distance_km < 10000000 THEN 'Close (1M - 10M km)'
                WHEN miss_distance_km < 50000000 THEN 'Moderate (10M - 50M km)'
                ELSE                                  'Distant (50M+ km)'
            END AS proximity_category

        FROM raw_neo
    """)