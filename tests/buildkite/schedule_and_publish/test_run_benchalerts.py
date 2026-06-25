import json
import subprocess
from typing import Optional

import sqlalchemy as s

from buildkite.schedule_and_publish.get_commits import get_commits
from buildkite.schedule_and_publish.run_benchalerts import run_benchalerts
from config import Config
from models.benchmarkable import Benchmarkable
from models.run import Run
from tests.helpers import (machine_configs,
                           make_github_webhook_event_for_comment,
                           outbound_requests, test_benchmarkable_id)

machines = list(machine_configs.keys())
report_url = "https://conbench.example/reports/1234"


def fake_conbench_ci_report(monkeypatch, status="failure"):
    calls = []
    monkeypatch.setattr(
        Config, "CONBENCH_URL", "http://mocked-integrations:9999/conbench"
    )

    def run(cmd, capture_output, text, check):
        calls.append(cmd)
        return subprocess.CompletedProcess(
            cmd,
            1 if status in ["failure", "action_required"] else 0,
            stdout=json.dumps(
                {
                    "status": status,
                    "status_reason": "benchmark regressions detected",
                    "report_url": report_url,
                    "summary": {
                        "runs": 2,
                        "contender_results": 20,
                        "compared": 18,
                        "analyzed": 18,
                        "regressions": 1,
                        "benchmark_errors": 0,
                    },
                }
            )
            + "\n",
            stderr="",
        )

    monkeypatch.setattr("models.benchalerts_run.subprocess.run", run)
    return calls


def flag_value(cmd, flag):
    index = cmd.index(flag)
    return cmd[index + 1]


def last_pr_comment_body_posted() -> Optional[str]:
    """Return the body of the last comment posted on the PR, or None if there isn't one."""
    pr_urls = [
        "http://mocked-integrations:9999/github/repos/apache/arrow/issues/1234/comments",
        "http://mocked-integrations:9999/github/repos/apache/arrow/issues/10973/comments",
    ]
    for url, response_data in reversed(outbound_requests):
        if url in pr_urls:
            return json.loads(response_data)["body"]
    return None


def assert_last_pr_comment_was_pending():
    expected_comment_body = (
        f"Benchmark runs are scheduled for commit {test_benchmarkable_id}. "
        f"Watch https://buildkite.com/{Config.BUILDKITE_ORG} and {Config.CONBENCH_URL} "
        "for updates. A comment will be posted here when the runs are complete."
    )
    assert last_pr_comment_body_posted()
    assert last_pr_comment_body_posted() == expected_comment_body


def assert_no_pr_comment_was_posted():
    assert last_pr_comment_body_posted() is None


def test_run_benchalerts_on_pr_request(client, monkeypatch):
    outbound_requests.clear()
    conbench_calls = fake_conbench_ci_report(monkeypatch)

    make_github_webhook_event_for_comment(
        client, comment_body="@ursabot please benchmark"
    )
    run_benchalerts()
    assert_last_pr_comment_was_pending()

    # Only finish one of the machines
    for run in Run.all():
        if run.machine_name == machines[0]:
            run.finished_at = s.sql.func.now()
            run.status = "finished"
            run.save()

    run_benchalerts()
    assert_last_pr_comment_was_pending()
    assert conbench_calls == []

    # Finish the other machine
    for run in Run.all():
        if run.machine_name == machines[1]:
            run.finished_at = s.sql.func.now()
            run.status = "finished"
            run.save()

    run_benchalerts()
    assert len(conbench_calls) == 1
    cmd = conbench_calls[0]
    assert cmd[:3] == ["conbench-v2", "ci", "report"]
    assert flag_value(cmd, "--server") == Config.CONBENCH_URL
    assert flag_value(cmd, "--repository") == "https://github.com/apache/arrow"
    assert flag_value(cmd, "--commit") == test_benchmarkable_id
    assert "--baseline-run-ids" in cmd
    assert "--baseline" not in cmd
    assert flag_value(cmd, "--github-pr-number") == "1234"
    assert "--github-check" in cmd
    assert "--github-pr-comment" in cmd

    # Verify pull comment was marked finished since all runs have status = "finished"
    benchalerts_run = Benchmarkable.get(test_benchmarkable_id).benchalerts_runs[0]
    assert benchalerts_run.finished_at
    assert benchalerts_run.status == "failure"
    assert benchalerts_run.check_link == report_url
    assert benchalerts_run.pr_comment_link == report_url


def test_run_benchalerts_on_merged_pull_requests(monkeypatch):
    outbound_requests.clear()
    conbench_calls = fake_conbench_ci_report(monkeypatch)

    get_commits()
    contender = Benchmarkable.get("f2f663be0a87e13c9cd5403dea51379deb4cf04d")
    baseline = Benchmarkable.get("c6fdeaf9fb85622242963dc28660e9592088986c")

    # Verify Pull Request is not updated when no runs are finished
    run_benchalerts()
    assert_no_pr_comment_was_posted()

    # Verify Pull Request is not updated when only baseline runs are finished
    for run in baseline.runs:
        run.finished_at = s.sql.func.now()
        run.status = "finished"
        run.save()

    run_benchalerts()
    assert_no_pr_comment_was_posted()

    # Verify Pull Request is updated when baseline and contender runs are finished
    for run in contender.runs:
        run.finished_at = s.sql.func.now()
        run.status = "finished"
        run.save()

    run_benchalerts()
    assert len(conbench_calls) == 1
    cmd = conbench_calls[0]
    assert cmd[:3] == ["conbench-v2", "ci", "report"]
    assert flag_value(cmd, "--server") == Config.CONBENCH_URL
    assert flag_value(cmd, "--repository") == "https://github.com/apache/arrow"
    assert flag_value(cmd, "--commit") == contender.id
    assert "--baseline-run-ids" in cmd
    assert "--baseline" not in cmd
    assert flag_value(cmd, "--github-pr-number") == str(contender.pull_number)
    assert "--github-check" in cmd
    assert "--github-pr-comment" in cmd

    assert contender.benchalerts_runs[0].finished_at
    assert contender.benchalerts_runs[0].status == "failure"
