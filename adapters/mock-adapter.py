import json
import os
import uuid
from pathlib import Path

RESULTS_DICT = {
    "run_name": "very-real-benchmark",
    "run_id": "ezf69672dc3741259aac97650414a18c",
    "batch_id": "1z21bd2477d04ca8be0f4bad58c61757",
    "run_reason": None,
    "timestamp": "2202-09-16T15:42:27.527948+00:00",
    "stats": {
        "data": [1.1, 2.2, 3.3],
        "unit": "ns",
        "times": [3.3, 2.2, 1.1],
        "time_unit": "ns",
    },
    "tags": {
        "name": "very-real-benchmark",
        "suite": "dope-benchmarks",
        "source": "app-micro",
    },
    "info": {},
    "context": {"benchmark_language": "A++"},
    "github": {
        "commit": "2z8c9c49a5dc4a179243268e4bb6daa5",
        "repository": "git@github.com:conchair/conchair",
    },
}


def write_result_payload(payload):
    results_dir = Path(os.environ.get("CONBENCH_RESULTS_DIR", "bench-results"))
    results_dir.mkdir(parents=True, exist_ok=True)
    path = results_dir / f"result-{uuid.uuid4().hex}.json"
    tmp_path = path.with_name(path.name + ".tmp")
    tmp_path.write_text(
        json.dumps(payload, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    tmp_path.replace(path)
    return path


if __name__ == "__main__":
    output_path = write_result_payload(RESULTS_DICT)
    print(f"Wrote Conbench result payload: {output_path}")
