# Arrow Benchmarks CI

Buildkite orchestration and Arrow benchmark scheduling for Conbench migration
work. This fork is part of the Conbench v2 migration path and currently targets
branch `v2-conbench-ci-report` on `wesm/arrow-benchmarks-ci`.

## Agent workflow

- Commit repository changes before ending the turn unless the user explicitly
  asks not to commit. Keep unrelated user changes out of commits; stage only
  the paths you changed for the task.
- Keep deployment changes reproducible and IaC-backed. Do not create one-off
  Kubernetes resources, Route53 records, AWS console edits, or host-local
  processes as part of the maintained migration path.
- Do not commit secrets, `.tfvars`, Buildkite tokens, database URLs, GitHub App
  private keys, or full environment dumps.
- Do not add tautological content-matching tests that only assert that strings,
  labels, headings, or resource names you just wrote are still present. Tests
  must verify behavior or a meaningful contract: parse structured output when
  possible, exercise code paths, validate rendered artifacts with an external
  consumer, or check invariants that would catch a real regression.

## Conbench v2 migration

- Use the Go `conbench` CLI for v2 result submission and CI reports. In this
  repo the binary may be named `conbench-v2` to avoid colliding with legacy
  Python runner commands.
- The supported publishing boundary is JSON payload files plus
  `conbench results submit`; do not reintroduce legacy email/password,
  `.conbench`, `benchclients`, `benchconnect`, or `benchalerts` publishing.
- Terraform under `terraform/` is the source of truth for Arrow AWS deployment
  resources. Review plans before applying and never run `terraform apply` unless
  the user explicitly approves the exact target.

## Validation

- For Python changes, prefer focused `pytest` invocations that exercise the
  changed path. Existing Docker-based test commands are documented in
  `README.md`.
- For Terraform changes, run `terraform fmt` and `terraform validate` when a
  Terraform binary is available. If it is not available, state that clearly and
  run only non-tautological static checks.
- Always run `git diff --check` before committing.
