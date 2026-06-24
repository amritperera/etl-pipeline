from datetime import datetime, timedelta
from airflow.sdk import dag, task


@dag(
    dag_id="neo_pipeline",
    description="Ingest and transform NASA Near Earth Object data",
    schedule="@daily",
    start_date=datetime(2026, 6, 1),
    catchup=False,
    default_args={
        "retries": 1,
        "retry_delay": timedelta(minutes=5),
    },
    tags=["nasa", "neo", "portfolio"],
)
def neo_pipeline():

    @task
    def ingest():
        import sys
        sys.path.insert(0, "/opt/airflow/src")
        from ingestion.fetch_neo import fetch_neo_data, parse_neo_data, load_to_duckdb
        from datetime import datetime, timedelta, timezone

        end_date = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        start_date = (datetime.now(timezone.utc) - timedelta(days=7)).strftime("%Y-%m-%d")

        db_path = "/opt/airflow/data/neo_pipeline.duckdb"

        raw = fetch_neo_data(start_date, end_date)
        df = parse_neo_data(raw)
        load_to_duckdb(df, db_path)

        return f"Ingested {len(df)} records"

    @task
    def transform():
        import sys
        sys.path.insert(0, "/opt/airflow/src")
        from transform.transform_neo import transform_neo

        db_path = "/opt/airflow/data/neo_pipeline.duckdb"
        transform_neo(db_path)

        return "Transform complete"

    ingest_result = ingest()
    transform_result = transform()
    ingest_result >> transform_result


neo_pipeline()