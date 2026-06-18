import logging
import sys
from datetime import datetime, timedelta, timezone
from ingestion.fetch_neo import fetch_neo_data, parse_neo_data, load_to_duckdb
from transform.transform_neo import transform_neo

# set up logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s — %(levelname)s — %(message)s",
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler(r"C:\Amrit_Database\etl-pipeline\logs\pipeline.log")
    ]
)
logger = logging.getLogger(__name__)

DB_PATH = r"C:\Amrit_Database\etl-pipeline\data\neo_pipeline.duckdb"


def run_pipeline(start_date: str = None, end_date: str = None) -> None:
    """
    Run the full NEO pipeline: ingest → transform.
    Defaults to the last 7 days if no dates provided.
    """
    logger.info("=" * 50)
    logger.info("NEO PIPELINE STARTING")
    logger.info("=" * 50)

    # default to last 7 days
    if not end_date:
        end_date = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    if not start_date:
        start_date = (datetime.now(timezone.utc) - timedelta(days=7)).strftime("%Y-%m-%d")

    logger.info(f"Date range: {start_date} to {end_date}")

    # step 1 — ingest
    logger.info("STEP 1: Ingestion")
    raw = fetch_neo_data(start_date, end_date)
    df = parse_neo_data(raw)
    load_to_duckdb(df, DB_PATH)

    # step 2 — transform
    logger.info("STEP 2: Transform")
    transform_neo(DB_PATH)

    logger.info("=" * 50)
    logger.info("NEO PIPELINE COMPLETE")
    logger.info("=" * 50)


if __name__ == "__main__":
    run_pipeline()