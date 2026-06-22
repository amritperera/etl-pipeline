import sys
import os
import duckdb
import pytest

# allow imports from src/
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from ingestion.fetch_neo import parse_neo_data, load_to_duckdb
from transform.transform_neo import transform_neo, validate_neo_data


# same shape NASA actually returns — reused from test_ingestion.py
SAMPLE_API_RESPONSE = {
    "element_count": 2,
    "near_earth_objects": {
        "2026-06-20": [
            {
                "id": "3001",
                "name": "(2026 INT1)",
                "nasa_jpl_url": "http://test.com/3001",
                "is_potentially_hazardous_asteroid": False,
                "is_sentry_object": False,
                "absolute_magnitude_h": 21.5,
                "estimated_diameter": {
                    "kilometers": {
                        "estimated_diameter_min": 0.05,
                        "estimated_diameter_max": 0.12
                    }
                },
                "close_approach_data": [
                    {
                        "close_approach_date": "2026-06-20",
                        "relative_velocity": {"kilometers_per_hour": "42000.5"},
                        "miss_distance": {"kilometers": "3200000.5"},
                        "orbiting_body": "Earth"
                    }
                ]
            }
        ],
        "2026-06-21": [
            {
                "id": "3002",
                "name": "(2026 INT2)",
                "nasa_jpl_url": "http://test.com/3002",
                "is_potentially_hazardous_asteroid": True,
                "is_sentry_object": False,
                "absolute_magnitude_h": 17.8,
                "estimated_diameter": {
                    "kilometers": {
                        "estimated_diameter_min": 0.4,
                        "estimated_diameter_max": 0.9
                    }
                },
                "close_approach_data": [
                    {
                        "close_approach_date": "2026-06-21",
                        "relative_velocity": {"kilometers_per_hour": "61000.0"},
                        "miss_distance": {"kilometers": "900000.0"},
                        "orbiting_body": "Earth"
                    }
                ]
            }
        ]
    }
}


@pytest.fixture
def temp_db_path(tmp_path):
    """
    pytest's tmp_path gives us a real temporary file on disk that's
    automatically cleaned up after the test — this lets us test against
    an actual DuckDB file, not just an in-memory mock.
    """
    return str(tmp_path / "integration_test.duckdb")


def test_full_pipeline_parse_load_transform(temp_db_path):
    """
    End-to-end check: real parse_neo_data() output flows through
    load_to_duckdb() and transform_neo() without any layer being
    mocked or hand-inserted.
    """
    # step 1: parse real sample JSON (same function used in production)
    df = parse_neo_data(SAMPLE_API_RESPONSE)
    assert len(df) == 2

    # step 2: load that real DataFrame into an actual DuckDB file
    load_to_duckdb(df, temp_db_path)

    con = duckdb.connect(temp_db_path)
    raw_count = con.execute("SELECT COUNT(*) FROM raw_neo").fetchone()[0]
    assert raw_count == 2

    # step 3: run the real transform layer against that loaded data
    transform_neo(temp_db_path)

    fct_count = con.execute("SELECT COUNT(*) FROM fct_neo").fetchone()[0]
    assert fct_count == 2

    con.close()


def test_full_pipeline_preserves_hazardous_flag(temp_db_path):
    """
    The hazardous flag set during parsing should survive the full
    journey through loading and transformation unchanged.
    """
    df = parse_neo_data(SAMPLE_API_RESPONSE)
    load_to_duckdb(df, temp_db_path)
    transform_neo(temp_db_path)

    con = duckdb.connect(temp_db_path)
    hazardous_count = con.execute(
        "SELECT COUNT(*) FROM fct_neo WHERE is_potentially_hazardous = true"
    ).fetchone()[0]
    con.close()

    assert hazardous_count == 1  # only object 3002 was marked hazardous


def test_full_pipeline_validation_passes_on_real_flow(temp_db_path):
    """
    Validation should pass when run against data that actually came
    through parsing and loading, not hand-crafted insert statements.
    """
    df = parse_neo_data(SAMPLE_API_RESPONSE)
    load_to_duckdb(df, temp_db_path)
    transform_neo(temp_db_path)  # validate_neo_data runs inside this

    # if we got here without an exception, validation passed
    con = duckdb.connect(temp_db_path)
    count = con.execute("SELECT COUNT(*) FROM fct_neo").fetchone()[0]
    con.close()
    assert count == 2


def test_full_pipeline_handles_rerun_without_duplicating(temp_db_path):
    """
    Running the same data through the pipeline twice should not create
    duplicate rows — this tests the dedup logic in load_to_duckdb()
    in a real end-to-end context, not just in isolation.
    """
    df = parse_neo_data(SAMPLE_API_RESPONSE)

    load_to_duckdb(df, temp_db_path)
    load_to_duckdb(df, temp_db_path)  # same data, run again

    con = duckdb.connect(temp_db_path)
    raw_count = con.execute("SELECT COUNT(*) FROM raw_neo").fetchone()[0]
    con.close()

    assert raw_count == 2  # not 4