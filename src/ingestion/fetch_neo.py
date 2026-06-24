import requests
import pandas as pd
import duckdb
import os
import logging
from datetime import datetime, timedelta, timezone
from dotenv import load_dotenv
import os as _os

# load environment variables — look in the project root explicitly
_env_path = _os.path.join(_os.path.dirname(__file__), "..", "..", ".env")
load_dotenv(_env_path)
API_KEY = os.getenv("NASA_API_KEY")

# set up logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s — %(levelname)s — %(message)s"
)
logger = logging.getLogger(__name__)


def fetch_neo_data(start_date: str, end_date: str) -> dict:
    """
    Fetch Near Earth Object data from NASA NeoWs API.
    Date format: YYYY-MM-DD. Max range is 7 days per request.
    """
    url = "https://api.nasa.gov/neo/rest/v1/feed"
    params = {
        "start_date": start_date,
        "end_date": end_date,
        "api_key": API_KEY
    }

    logger.info(f"Fetching NEO data from {start_date} to {end_date}")
    response = requests.get(url, params=params, timeout=30)
    response.raise_for_status()

    data = response.json()
    logger.info(f"API returned {data['element_count']} near earth objects")
    return data


def parse_neo_data(raw_data: dict) -> pd.DataFrame:
    """
    Parse raw API response into a flat DataFrame.
    """
    records = []

    for date, objects in raw_data["near_earth_objects"].items():
        for obj in objects:
            close_approach = obj["close_approach_data"][0] if obj["close_approach_data"] else {}
            records.append({
                "neo_id":                   obj["id"],
                "neo_name":                 obj["name"],
                "nasa_jpl_url":             obj["nasa_jpl_url"],
                "is_potentially_hazardous": obj["is_potentially_hazardous_asteroid"],
                "is_sentry_object":         obj["is_sentry_object"],
                "abs_magnitude":            obj["absolute_magnitude_h"],
                "min_diameter_km":          obj["estimated_diameter"]["kilometers"]["estimated_diameter_min"],
                "max_diameter_km":          obj["estimated_diameter"]["kilometers"]["estimated_diameter_max"],
                "close_approach_date":      close_approach.get("close_approach_date"),
                "relative_velocity_kmh":    float(close_approach.get("relative_velocity", {}).get("kilometers_per_hour", 0)),
                "miss_distance_km":         float(close_approach.get("miss_distance", {}).get("kilometers", 0)),
                "orbiting_body":            close_approach.get("orbiting_body"),
                "ingested_at":              datetime.now(timezone.utc).isoformat()
            })

    df = pd.DataFrame(records)
    logger.info(f"Parsed {len(df)} NEO records into DataFrame")
    return df


def load_to_duckdb(df: pd.DataFrame, db_path: str) -> None:
    """
    Load parsed NEO data into DuckDB raw schema.
    """
    con = duckdb.connect(db_path)

    try:
        con.execute("""
            CREATE TABLE IF NOT EXISTS raw_neo (
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

        # avoid duplicates on re-run
        existing_ids = con.execute("SELECT neo_id FROM raw_neo").fetchdf()["neo_id"].tolist()
        new_records = df[~df["neo_id"].isin(existing_ids)]

        if len(new_records) > 0:
            con.execute("INSERT INTO raw_neo SELECT * FROM new_records")
            logger.info(f"Inserted {len(new_records)} new records into raw_neo")
        else:
            logger.info("No new records to insert — all already exist")
    finally:
        con.close()


if __name__ == "__main__":
    # pull last 7 days of data
    end_date = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    start_date = (datetime.now(timezone.utc) - timedelta(days=7)).strftime("%Y-%m-%d")

    db_path = r"C:\Amrit_Database\etl-pipeline\data\neo_pipeline.duckdb"

    raw = fetch_neo_data(start_date, end_date)
    df = parse_neo_data(raw)
    load_to_duckdb(df, db_path)

    print(f"\nDone. {len(df)} records processed.")
    print(df[["neo_name", "is_potentially_hazardous", "miss_distance_km", "relative_velocity_kmh"]].head(10))