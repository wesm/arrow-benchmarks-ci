#!/usr/bin/env bash
set -euo pipefail

repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$repo_root"

# Load benchmark utility functions without invoking the dispatcher at EOF.
set --
source "$repo_root/buildkite/benchmark/utils.sh"

export CONBENCH_RESULTS_DIR="${CONBENCH_RESULTS_DIR:-$repo_root/bench-results/${BUILDKITE_BUILD_ID:-local-v2-adapter-smoke}}"
export CONBENCH_CLI="${CONBENCH_CLI:-conbench-v2}"
export RUN_ID="${RUN_ID:-${BUILDKITE_BUILD_ID:-local-v2-adapter-smoke}}"
export RUN_NAME="${RUN_NAME:-conbench v2 adapter smoke: ${BUILDKITE_BUILD_ID:-local}}"
export RUN_REASON="${RUN_REASON:-manual-smoke}"
export CONBENCH_MACHINE_INFO_NAME="${CONBENCH_MACHINE_INFO_NAME:-${MACHINE:-conbench-v2-smoke-linux}}"
export CONBENCH_PROJECT_REPOSITORY="${CONBENCH_PROJECT_REPOSITORY:-https://github.com/apache/arrow}"
export CONBENCH_PROJECT_COMMIT="${CONBENCH_PROJECT_COMMIT:-${BUILDKITE_COMMIT:-1111111111111111111111111111111111111111}}"

submit_out="${CONBENCH_SUBMIT_OUT:-conbench-submit.jsonl}"
mkdir -p "$CONBENCH_RESULTS_DIR"

ensure_conbench_cli
check_conbench_submit_env

"${PYTHON:-python3}" adapters/mock-adapter.py

payload_count=$(find "$CONBENCH_RESULTS_DIR" -maxdepth 1 -type f -name '*.json' | wc -l | tr -d ' ')
echo "Conbench v2 adapter smoke payloads: $payload_count"
if [ "$payload_count" = "0" ]; then
  echo "No Conbench result payloads found in $CONBENCH_RESULTS_DIR" >&2
  exit 1
fi

set -o pipefail
"$CONBENCH_CLI" results submit \
  "$CONBENCH_RESULTS_DIR/*.json" \
  --server "$CONBENCH_URL" \
  --jobs "${CONBENCH_SUBMIT_JOBS:-4}" | tee "$submit_out"
