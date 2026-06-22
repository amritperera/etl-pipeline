import sys
import os
import responses
import pandas as pd

# allow imports from src/
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from ingestion.fetch_neo import fetch_neo_data, parse_neo_data


# a small, realistic sample of what the NASA API actually returns
SAMPLE_API_RESPONSE = {
    "element_count": 2,
    "near_earth_objects": {
        "2026-06-20": [
            {
                "id": "2001",
                "name": "(2026 AB1)",
                "nasa_jpl_url": "http://test.com/2001",
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
                "id": "2002",
                "name": "(2026 CD2)",
                "nasa_jpl_url": "http://test.com/2002",
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


@responses.activate
def test_fetch_neo_data_calls_correct_url():
    """fetch_neo_data should hit the NASA NeoWs feed endpoint and return JSON."""
    responses.add(
        responses.GET,
        "https://api.nasa.gov/neo/rest/v1/feed",
        json=SAMPLE_API_RESPONSE,
        status=200
    )

    result = fetch_neo_data("2026-06-20", "2026-06-21")

    assert result["element_count"] == 2
    assert "near_earth_objects" in result


def test_parse_neo_data_returns_correct_row_count():
    """parse_neo_data should flatten both days into one row per object."""
    df = parse_neo_data(SAMPLE_API_RESPONSE)
    assert len(df) == 2


def test_parse_neo_data_extracts_hazardous_flag_correctly():
    """The hazardous flag should be parsed correctly per object."""
    df = parse_neo_data(SAMPLE_API_RESPONSE)

    obj_2001 = df[df["neo_id"] == "2001"].iloc[0]
    obj_2002 = df[df["neo_id"] == "2002"].iloc[0]

    assert obj_2001["is_potentially_hazardous"] == False
    assert obj_2002["is_potentially_hazardous"] == True


def test_parse_neo_data_handles_missing_close_approach_gracefully():
    """If an object has no close_approach_data, parsing shouldn't crash."""
    broken_response = {
        "element_count": 1,
        "near_earth_objects": {
            "2026-06-20": [
                {
                    "id": "9999",
                    "name": "(No Approach Data)",
                    "nasa_jpl_url": "http://test.com/9999",
                    "is_potentially_hazardous_asteroid": False,
                    "is_sentry_object": False,
                    "absolute_magnitude_h": 25.0,
                    "estimated_diameter": {
                        "kilometers": {
                            "estimated_diameter_min": 0.01,
                            "estimated_diameter_max": 0.02
                        }
                    },
                    "close_approach_data": []
                }
            ]
        }
    }

    df = parse_neo_data(broken_response)
    assert len(df) == 1
    assert df.iloc[0]["close_approach_date"] is None


def test_parse_neo_data_returns_correct_dtypes():
    """Velocity and distance fields should be parsed as floats, not strings."""
    df = parse_neo_data(SAMPLE_API_RESPONSE)

    assert df["relative_velocity_kmh"].dtype == float
    assert df["miss_distance_km"].dtype == float