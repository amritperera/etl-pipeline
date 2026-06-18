import logging
import os
import sys
from datetime import datetime, timedelta, timezone

# set up logging FIRST before any other imports
log_path = r"C:\Amrit_Database\etl-pipeline\logs\pipeline.log"
os.makedirs(os.path.dirname(log_path), exist_ok=True)

root_logger = logging.getLogger()
root_logger.setLevel(logging.INFO)

formatter = logging.Formatter("%(asctime)s — %(levelname)s — %(message)s")

console_handler = logging.StreamHandler(sys.stdout)
console_handler.setFormatter(formatter)

file_handler = logging.FileHandler(log_path, mode="a", encoding="utf-8")
file_handler.setFormatter(formatter)

root_logger.addHandler(console_handler)
root_logger.addHandler(file_handler)

# now import modules AFTER logging is configured
from ingestion.fetch_neo import fetch_neo_data, parse_neo_data, load_to_duckdb
from transform.transform_neo import transform_neo

logger = logging.getLogger(__name__)

DB_PATH = r"C:\Amrit_Database\etl-pipeline\data\neo_pipeline.duckdb"


def run_pipeline(start_date: str = None, end_date: str = None) -> None:
    logger.info("=" * 50)
    logger.info("NEO PIPELINE STARTING")
    logger.info("=" * 50)

    if not end_date:
        end_date = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    if not start_date:
        start_date = (datetime.now(timezone.utc) - timedelta(days=7)).strftime("%Y-%m-%d")

    logger.info(f"Date range: {start_date} to {end_date}")

    logger.info("STEP 1: Ingestion")
    raw = fetch_neo_data(start_date, end_date)
    df = parse_neo_data(raw)
    load_to_duckdb(df, DB_PATH)

    logger.info("STEP 2: Transform")
    transform_neo(DB_PATH)

    logger.info("=" * 50)
    logger.info("NEO PIPELINE COMPLETE")
    logger.info("=" * 50)


if __name__ == "__main__":
    run_pipeline()