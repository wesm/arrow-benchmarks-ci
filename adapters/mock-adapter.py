import json
import os
import uuid
from datetime import datetime, timezone
from pathlib import Path


def env_or_none(name):
    value = os.environ.get(name)
    return value if value else None


def build_payload():
    run_id = os.environ.get("RUN_ID", f"local-smoke-{uuid.uuid4().hex}")
    github = {
        "commit": os.environ.get(
            "CONBENCH_PROJECT_COMMIT",
            os.environ.get("BENCHMARKABLE", "1111111111111111111111111111111111111111"),
        ),
        "repository": os.environ.get(
            "CONBENCH_PROJECT_REPOSITORY",
            "https://github.com/apache/arrow",
        ),
    }
    pr_number = env_or_none("CONBENCH_PROJECT_PR_NUMBER") or env_or_none(
        "BENCHMARKABLE_PR_NUMBER"
    )
    if pr_number is not None:
        github["pr_number"] = int(pr_number)

    return {
        "run_name": os.environ.get("RUN_NAME", "Conbench v2 adapter smoke"),
        "run_id": run_id,
        "batch_id": os.environ.get("BATCH_ID", run_id),
        "run_reason": env_or_none("RUN_REASON"),
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "machine_info": {
            "name": os.environ.get(
                "CONBENCH_MACHINE_INFO_NAME",
                os.environ.get("MACHINE", "conbench-v2-smoke"),
            )
        },
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
        "context": {"benchmark_language": "Python"},
        "github": github,
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
    output_path = write_result_payload(build_payload())
    print(f"Wrote Conbench result payload: {output_path}")
