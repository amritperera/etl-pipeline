import duckdb
import logging
from datetime import datetime, timezone

# set up logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s — %(levelname)s — %(message)s"
)
logger = logging.getLogger(__name__)

def validate_neo_data(con) -> None:
    """
    Run data quality checks against fct_neo.
    Raises an exception if any check fails.
    """
    checks_passed = []
    checks_failed = []

    # check 1: no null neo_ids
    null_ids = con.execute(
        "SELECT COUNT(*) FROM fct_neo WHERE neo_id IS NULL"
    ).fetchone()[0]
    if null_ids == 0:
        checks_passed.append("No null neo_ids")
    else:
        checks_failed.append(f"{null_ids} rows with null neo_id")

    # check 2: no duplicate neo_ids
    dupes = con.execute("""
        SELECT COUNT(*) FROM (
            SELECT neo_id, COUNT(*) as cnt
            FROM fct_neo
            GROUP BY neo_id
            HAVING cnt > 1
        )
    """).fetchone()[0]
    if dupes == 0:
        checks_passed.append("No duplicate neo_ids")
    else:
        checks_failed.append(f"{dupes} duplicate neo_ids found")

    # check 3: miss_distance_km should never be negative
    negative_distance = con.execute(
        "SELECT COUNT(*) FROM fct_neo WHERE miss_distance_km < 0"
    ).fetchone()[0]
    if negative_distance == 0:
        checks_passed.append("No negative miss distances")
    else:
        checks_failed.append(f"{negative_distance} rows with negative miss_distance_km")

    # check 4: diameter values should be positive
    bad_diameter = con.execute(
        "SELECT COUNT(*) FROM fct_neo WHERE avg_diameter_km <= 0"
    ).fetchone()[0]
    if bad_diameter == 0:
        checks_passed.append("All diameters positive")
    else:
        checks_failed.append(f"{bad_diameter} rows with zero/negative diameter")

    logger.info(f"Validation passed: {len(checks_passed)} checks")
    for check in checks_passed:
        logger.info(f"  ✓ {check}")

    if checks_failed:
        logger.error(f"Validation FAILED: {len(checks_failed)} checks")
        for check in checks_failed:
            logger.error(f"  ✗ {check}")
        raise ValueError(f"Data validation failed: {checks_failed}")

def transform_neo(db_path: str) -> None:
    """
    Transform raw NEO data into analytics-ready tables.
    Reads from raw_neo, writes to fct_neo and dim_hazard_summary.
    """
    con = duckdb.connect(db_path)

    try: 
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

        # run validation checks
        validate_neo_data(con)
    finally:
        con.close()


if __name__ == "__main__":
    db_path = r"C:\Amrit_Database\etl-pipeline\data\neo_pipeline.duckdb"
    transform_neo(db_path)
    print("\nTransform complete.")