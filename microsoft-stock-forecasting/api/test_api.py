"""Run Phase 5 API checks and save actual responses for the report.
Start the API server first: python -m uvicorn api.main:app --reload
"""

import json
from pathlib import Path
import requests

BASE = "http://127.0.0.1:8000"
ROOT = Path(__file__).resolve().parent.parent
results = {}


def call(method, url, **kwargs):
    response = requests.request(method, BASE + url, timeout=15, **kwargs)
    response.raise_for_status()
    return response.json()


example = {
    "date": "2099-12-30T16:00:00",
    "open": 100.0,
    "high": 105.0,
    "low": 98.0,
    "close": 102.0,
    "volume": 100000,
}

for database in ("sql", "mongo"):
    prefix = f"/{database}/stocks"
    print(f"\nTesting {database.upper()} endpoints...")
    results[database] = {
        "latest": call("GET", prefix + "/latest"),
        "range": call("GET", prefix + "/range", params={
            "start": "2020-01-01T00:00:00", "end": "2020-01-31T23:59:59"
        }),
        "history_count": len(call("GET", prefix, params={"limit": 60})),
    }

    record_id = None
    try:
        created = call("POST", prefix, json=example)
        record_id = created["id"]
        results[database]["created"] = created
        results[database]["read"] = call("GET", prefix + f"/{record_id}")

        modified = {**example, "close": 103.0}
        results[database]["updated"] = call(
            "PUT", prefix + f"/{record_id}", json=modified
        )
    finally:
        if record_id is not None:
            results[database]["deleted"] = call(
                "DELETE", prefix + f"/{record_id}"
            )

    print("Create, read, update, delete, latest, range: successful")

output_dir = ROOT / "outputs" / "api_results"
output_dir.mkdir(parents=True, exist_ok=True)
path = output_dir / "phase5_test_results.json"
path.write_text(json.dumps(results, indent=2), encoding="utf-8")
print(f"\nSaved actual responses to {path}")
