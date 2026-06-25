# Conbench v2 Buildkite Smoke Test Plan

This plan defines the first safe Buildkite validation path for the Conbench v2
migration work in `wesm/arrow-benchmarks-ci`.

The smoke path must prove three things before any production Arrow pull request
receives Conbench output:

- benchmark jobs can emit Conbench v2 payload files and submit them with the Go
  CLI,
- Buildkite keeps enough logs and artifacts to debug failed runs, and
- GitHub Check Run and pull request comment publishing can be validated on a
  non-production pull request.

## Pipeline

Create a temporary Buildkite pipeline named `conbench-v2-smoke`.

Use the `wesm/arrow-benchmarks-ci` repository, branch
`v2-conbench-ci-report`, and the benchmark runner command from
`buildkite/benchmark/pipeline.yml`:

```bash
source buildkite/benchmark/utils.sh create_conda_env_and_run_benchmarks
```

The first smoke should run as a manually triggered Buildkite build. After the
standalone benchmark runner works, run the broader scheduler path through
`buildkite/benchmark-test/pipeline.yml`, which creates benchmark builds through
the Buildkite API.

Do not point this pipeline at the production Conbench deployment or production
Apache Arrow pull requests during initial validation.

## Adapter Preflight

Before building Arrow or running the benchmark repositories, validate the
Buildkite secret, network, artifact, and v2 submit path with the mock adapter in
this repository. Use the repo-local preflight script on the same agent queue:

```bash
set -euo pipefail

scripts/conbench-v2-adapter-smoke.sh
```

The adapter writes a normal Conbench v2 payload using the same run, machine,
repository, commit, and optional pull request environment variables as the real
benchmark forks. It is not performance evidence, but it proves the reporter
token and endpoint before a long benchmark job starts.

## Buildkite Setup Prerequisites

The Buildkite account needs:

- a hosted or self-managed agent queue that can run the benchmark runner,
- outbound network access to the non-production Conbench v2 endpoint,
- Docker, Git, conda, and enough disk space for an Arrow checkout and build,
- access to a secret store or Buildkite environment hooks for sensitive values,
- permission to create the temporary `conbench-v2-smoke` pipeline, and
- for scheduler-path testing only, a Buildkite API token that can create builds
  in the same organization.

Use one small Linux worker first. Add macOS, arm64, and the larger Arrow
benchmark machines only after the Linux smoke is repeatable.

## Required Environment

Set these values on the `conbench-v2-smoke` pipeline or through Buildkite
secrets:

| Name | Secret | Purpose |
| --- | --- | --- |
| `CONBENCH_URL` | no | Non-production Conbench v2 endpoint, such as the prod-clone deployment. |
| `CONBENCH_TOKEN` | yes | Reporter API token minted by `conbench admin tokens create`. |
| `CONBENCH_CLI` | no | CLI executable name or path. Defaults to `conbench-v2`. |
| `CONBENCH_CLI_DOWNLOAD_URL` | no | Raw executable URL for the benchmark job to download when `CONBENCH_CLI` is not already on `PATH`. |
| `CONBENCH_CLI_INSTALL_COMMAND` | no | Shell command that installs `CONBENCH_CLI` when no download URL is used. Prefer a pinned commit or immutable artifact. |
| `CONBENCH_SUBMIT_JOBS` | no | Result submission parallelism. Defaults to `64` for one-file-per-result workloads; lower it if the endpoint or database shows pressure. |
| `BENCHMARKABLE_TYPE` | no | Use `arrow-commit` for the first smoke. |
| `BENCHMARKABLE` | no | Apache Arrow commit SHA to benchmark. Prefer a recent non-production test SHA. |
| `BENCHMARKABLE_PR_NUMBER` | no | Pull request number for report metadata when testing PR-shaped runs. |
| `FILTERS` | no | JSON benchmark filter. Start with one Python benchmark. |
| `MACHINE` | no | Stable machine name for Conbench, for example `conbench-v2-smoke-linux`. |
| `PYTHON_VERSION` | no | Python version for the benchmark environment, currently `3.12`. |
| `RUN_ID` | no | Use `$BUILDKITE_BUILD_ID` for manual smoke builds. |
| `RUN_NAME` | no | Human-readable run name, for example `conbench v2 smoke: $BUILDKITE_BUILD_ID`. |
| `RUN_REASON` | no | Use `pull-request` for PR-shaped validation and `manual-smoke` otherwise. |

Use this initial filter:

```json
{"langs":{"Python":{"names":["dataset-read"]}}}
```

The Conbench reporter token should be created by an operator on the Conbench
server or in an admin job with database access:

```bash
CONBENCH_DB_URL="$CONBENCH_DB_URL" conbench admin tokens create \
  --email ci@example.com \
  --user-name "Conbench CI Reporter" \
  --token-name buildkite-v2-smoke
```

Store only the returned plaintext token in Buildkite as `CONBENCH_TOKEN`.

## GitHub Reporting Environment

Validate GitHub publishing only against a scratch repository or a scratch pull
request in a fork. Do not post to production Apache Arrow pull requests until a
maintainer explicitly approves that step.

Preferred GitHub App settings:

| Name | Secret | Purpose |
| --- | --- | --- |
| `CONBENCH_CI_GITHUB_APP_ID` | no | GitHub App ID. The legacy `GITHUB_APP_ID` name also works. |
| `CONBENCH_CI_GITHUB_APP_PRIVATE_KEY` | yes | PEM private key contents. The legacy `GITHUB_APP_PRIVATE_KEY` name also works. |

Install the GitHub App on the scratch repository with permission to create Check
Runs and pull request issue comments.

For the first report-only validation, run `conbench ci report` manually in a
Buildkite command step after a successful submit:

```bash
"${CONBENCH_CLI:-conbench-v2}" ci report \
  --server "$CONBENCH_URL" \
  --repository "https://github.com/<owner>/<scratch-repo>" \
  --commit "$BENCHMARKABLE" \
  --run-ids "$RUN_ID" \
  --github-check \
  --github-pr-comment \
  --github-pr-number "$SCRATCH_PR_NUMBER" \
  --github-external-id "$BUILDKITE_BUILD_ID" \
  --build-url "$BUILDKITE_BUILD_URL" \
  --format json \
  --output conbench-ci-report.json
```

The scheduler-path smoke validates the same publishing path through
`buildkite/schedule_and_publish/run_benchalerts.py`, but that should wait until
standalone result submission is stable.

## Expected Artifacts

Buildkite always retains step logs. The smoke pipeline should also retain:

- result payloads from `**/bench-results/**/*.json`,
- Conbench submit output from `conbench-submit.jsonl`,
- CI report output from `conbench-ci-report.json`,
- any benchmark runner stderr/stdout visible in the Buildkite step log, and
- Arrow BCI API database rows only for the scheduler-path smoke.

The current benchmark runner writes result payloads under:

```text
<benchmark-repo>/bench-results/<RUN_ID>/*.json
```

Before `conbench results submit` runs, the benchmark runner prints the result
payload file count and total payload bytes. After submission, it prints the
number of JSONL rows written to `conbench-submit.jsonl` and the submit wall time
in seconds. These lines are the first place to look when deciding whether a
benchmark group needs lower submit parallelism or future batch-ingest work.

Before relying on a Buildkite run as migration evidence, confirm that the
pipeline uploads those JSON files as artifacts. If artifact upload is missing
from the pipeline settings, add:

```yaml
artifact_paths:
  - "**/bench-results/**/*.json"
  - "conbench-submit.jsonl"
  - "conbench-ci-report.json"
```

## Success Cases

Run these in order:

1. Adapter preflight without GitHub publishing.
   - The command exits `0`.
   - `bench-results/**/*.json` artifacts exist.
   - `conbench results submit` exits `0`.
   - The non-production Conbench UI shows the submitted smoke run.
2. Standalone benchmark smoke without GitHub publishing.
   - The benchmark step exits `0`.
   - `**/bench-results/**/*.json` artifacts exist.
   - `conbench results submit` exits `0`.
   - The non-production Conbench UI shows the submitted run for the smoke
     machine and commit.
3. Standalone CI report without GitHub publishing.
   - `conbench ci report --format json` exits `0` or `1`.
   - The JSON report has a typed `status` and, when available, a `report_url`.
   - Missing baseline data is reported as `action_required`, not as a transport
     or authentication error.
4. GitHub App smoke against a scratch pull request.
   - A Check Run named `Conbench performance report` appears on the scratch
     commit.
   - A pull request comment links to the Conbench report or Check Run.
   - No production Apache Arrow pull request receives a comment.
5. Scheduler-path smoke.
   - `buildkite/benchmark-test/pipeline.yml` creates one benchmark build for
     the selected machine.
   - `buildkite/schedule_and_publish/run_benchalerts.py` marks the run
     finished after benchmarks complete.
   - Stored report metadata includes the Conbench report status and link.

## Failure Cases

Run these probes before calling the migration path ready:

1. Invalid Conbench token.
   - Set `CONBENCH_TOKEN` to a bogus value.
   - The submit step fails visibly.
   - Benchmark result JSON artifacts are still retained.
2. Missing result payloads.
   - Run the submit command with an empty `CONBENCH_RESULTS_DIR`.
   - The step fails with `No Conbench result payloads found`.
3. Benchmark failure.
   - Use a temporary filter or command that exits nonzero.
   - The Buildkite job fails.
   - Step logs preserve the failing command and stderr.
   - Any payloads produced before failure remain available as artifacts.
4. GitHub App misconfiguration.
   - Remove the private key or install the App without Check Run permission.
   - `conbench ci report` fails before claiming publication.
   - No production PR is touched.

## Evidence To Record

For each successful smoke run, record the following in kata before closing the
corresponding migration issue:

- Buildkite build URL,
- Conbench endpoint used,
- branch and commit of `wesm/arrow-benchmarks-ci`,
- branch and commit of `wesm/benchmarks` and `wesm/arrowbench`, if used,
- selected `FILTERS`,
- count of uploaded result JSON artifacts,
- `Conbench payload files`, `Conbench payload bytes`,
  `Conbench submit rows`, and `Conbench submit seconds` from the Buildkite log,
- `conbench results submit` status,
- CI report status and report URL, and
- scratch GitHub PR URL when GitHub publishing is tested.

Never copy tokens, private keys, database URLs, or full environment dumps into
git, kata, Buildkite annotations, or public pull request comments.
