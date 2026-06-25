# arrow-benchmarks-ci

Arrow Benchmarks CI is responsible for
- orchestrating and prioritizing benchmark builds for [Apache Arrow](https://github.com/apache/arrow) based on
the [list of benchmarks](https://github.com/arctosalliance/benchmarks/blob/main/benchmarks.json) in [Benchmarks repo](https://github.com/arctosalliance/benchmarks)
- publishing benchmark results to [Apache Arrow](https://github.com/apache/arrow) pull requests associated with commits to master branch ([example](https://github.com/apache/arrow/pull/11843#issuecomment-986912639))
- posting benchmarks results to [Conbench](https://conbench.ursa.dev/)

Arrow Benchmarks CI consists of
- [Buildkite pipelines](https://buildkite.com/apache-arrow) and scripts for running benchmarks on [benchmark machines](https://github.com/arctosalliance/arrow-benchmarks-ci/blob/main/config.py#L47)
- Arrow BCI API service responsible for
    - listening to [apache/arrow](https://github.com/apache/arrow) Pull Request comment events
    so benchmark builds can be scheduled for pull requests with an `@ursabot please benchmark` comment
    - persisting benchmark build statistics (e.g., memory usage, run time, errors, and conda packages)

![Screenshot](arrow_bci_diagram.png)

#### Arrow Benchmarks CI Public Buildkite Pipelines
- [Arrow BCI Test](https://buildkite.com/apache-arrow/arrow-bci-test) is used for testing Arrow BCI API service and CI scripts

Note that you can view builds for these pipelines but you can not manually schedule new builds.

#### Conbench v2 migration smoke testing

The Conbench v2 migration branch uses the Go CLI for result submission and CI
report publishing. Before testing against production Apache Arrow pull requests,
use the temporary Buildkite smoke plan in
[Conbench v2 Buildkite Smoke Test Plan](docs/v2-conbench-smoke-test-plan.md).

#### How can I add my own benchmark machine to Arrow Benchmarks CI

Benchmark machines should be bare metal machines dedicated to only running benchmarks to
avoid high variability in benchmark results that can result in false regression/improvements.

Please use this doc to add a new benchmark machine: [How to Add New Benchmark Machine](docs/how-to-add-new-benchmark-machine.md)

#### How can I test benchmark builds that run on ursa-i9-9960x and ursa-thinkcentre-m75q locally
```bash
# Set env vars if benchmark results should be posted to v2 Conbench.
# The v2 CLI must be installed on PATH as conbench-v2, or set CONBENCH_CLI.
export CONBENCH_TOKEN=<conbench_api_token>
export CONBENCH_CLI=${CONBENCH_CLI:-conbench-v2}

# Build docker image with Arrow dependencies installed
cd ~/arrow-benchmarks-ci
docker build -f buildkite/benchmark-test/Dockerfile . -t benchmark-test

# Run benchmarks
docker run -i \
    --env BENCHMARKABLE=${BENCHMARKABLE:-"ac2d8ff481816299e2b047bf8a4546baccc3d050"} \
    --env BENCHMARKABLE_TYPE=${BENCHMARKABLE_TYPE:-"arrow-commit"} \
    --env BENCHMARKS_DATA_DIR="/data" \
    --env CONBENCH_TOKEN="$CONBENCH_TOKEN" \
    --env CONBENCH_CLI="$CONBENCH_CLI" \
    --env CONBENCH_URL="${CONBENCH_URL:-https://conbench.arrow-dev.org}" \
    --env MACHINE="docker-container-for-testing-benchmark-builds" \
    --env PYTHON_VERSION=${PYTHON_VERSION:-"3.8"} \
    --env RUN_ID=$BUILDKITE_BUILD_ID \
    --env RUN_NAME=${RUN_NAME:-"benchmark build test: $BUILDKITE_BUILD_ID"} \
    benchmark-test bash buildkite/benchmark/utils.sh create_conda_env_and_run_benchmarks
```

#### How can I test benchmark builds that run on Buildkite machines (ursa-i9-9960x, ursa-thinkcentre-m75q, etc)
This option is only available to [Apache Arrow CI Buildkite org](https://buildkite.com/apache-arrow/) users at the moment.

1. Go to https://buildkite.com/apache-arrow/arrow-bci-benchmark-build-test
2. Click New Build
    - Set `Commit` and `Branch` for `arrow-benchmarks-ci` repo's commit and branch that you would like to test
    - Click `Create Build`
    - Wait for `Pipeline upload` step to finish
    - Click on `Test Benchmark Builds` button
    - Select machines you want to run test builds on on
    ![Screenshot](test-benchmark-builds-popup.png)
    - Click `Continue`
    - Once `Test Benchmark Builds`, you will be able to monitor scheduled builds for selected
    `arrow-benchmarks-ci` repo's commit and branch
    under machines' `Arrow BCI Benchmark on ...` pipelines.

#### How to run tests
```bash
cd ~/arrow-benchmarks-ci
docker-compose -f envs/test/docker-compose.yml down
docker-compose -f envs/test/docker-compose.yml build
docker-compose -f envs/test/docker-compose.yml run app pytest -vv tests/
```
