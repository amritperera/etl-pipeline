import duckdb
import logging
from datetime import datetime, timezone

# set up logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s — %(levelname)s — %(message)s"
)
logger = logging.getLogger(__name__)


def transform_neo(db_path: str) -> None:
    """
    Transform raw NEO data into analytics-ready tables.
    Reads from raw_neo, writes to fct_neo and dim_hazard_summary.
    """
    con = duckdb.connect(db_path)

    logger.info("Creating fct_neo table...")
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

            -- size classification
            CASE
                WHEN avg_diameter_km < 0.01  THEN 'Small (< 10m)'
                WHEN avg_diameter_km < 0.1   THEN 'Medium (10m - 100m)'
                WHEN avg_diameter_km < 1.0   THEN 'Large (100m - 1km)'
                ELSE                              'Very Large (1km+)'
            END AS size_category,

            -- proximity classification
            CASE
                WHEN miss_distance_km < 1000000  THEN 'Very Close (< 1M km)'
                WHEN miss_distance_km < 10000000 THEN 'Close (1M - 10M km)'
                WHEN miss_distance_km < 50000000 THEN 'Moderate (10M - 50M km)'
                ELSE                                  'Distant (50M+ km)'
            END AS proximity_category

        FROM raw_neo
    """)
    logger.info("fct_neo created successfully")

    logger.info("Creating dim_hazard_summary table...")
    con.execute("""
        CREATE OR REPLACE TABLE dim_hazard_summary AS
        SELECT
            is_potentially_hazardous,
            size_category,
            COUNT(*)                            AS total_objects,
            round(AVG(miss_distance_km), 2)     AS avg_miss_distance_km,
            round(MIN(miss_distance_km), 2)     AS closest_approach_km,
            round(AVG(relative_velocity_kmh), 2)AS avg_velocity_kmh,
            round(MAX(relative_velocity_kmh), 2)AS max_velocity_kmh,
            round(AVG(avg_diameter_km), 6)      AS avg_diameter_km

        FROM fct_neo
        GROUP BY is_potentially_hazardous, size_category
        ORDER BY is_potentially_hazardous DESC, total_objects DESC
    """)
    logger.info("dim_hazard_summary created successfully")

    # quick sanity check
    count = con.execute("SELECT COUNT(*) FROM fct_neo").fetchone()[0]
    hazard_count = con.execute(
        "SELECT COUNT(*) FROM fct_neo WHERE is_potentially_hazardous = true"
    ).fetchone()[0]

    logger.info(f"fct_neo: {count} total objects, {hazard_count} potentially hazardous")

    con.close()


if __name__ == "__main__":
    db_path = r"C:\Amrit_Database\etl-pipeline\data\neo_pipeline.duckdb"
    transform_neo(db_path)
    print("\nTransform complete.")