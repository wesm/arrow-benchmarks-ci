import json
import os
import subprocess
from datetime import datetime
from typing import Optional, Union

import sqlalchemy as s
from sqlalchemy.dialects import postgresql
from sqlalchemy.orm import Mapped, mapped_column

from config import Config
from db import Base
from logger import log
from models.base import BaseMixin
from utils import generate_uuid


class BenchalertsRun(Base, BaseMixin):
    __tablename__ = "benchalerts_run"

    id: Mapped[str] = mapped_column(
        s.String, primary_key=True, default=generate_uuid, nullable=False
    )
    benchmarkable_id: Mapped[str] = mapped_column(
        s.String, s.ForeignKey("benchmarkable.id"), nullable=False
    )
    # Possibilities: <repo>-commit, pull-request, pyarrow-apache-wheel
    reason: Mapped[str] = mapped_column(s.String, nullable=False)

    finished_at: Mapped[Optional[datetime]] = mapped_column(
        s.DateTime(timezone=False), nullable=True
    )
    output: Mapped[Optional[Union[dict, list]]] = mapped_column(
        postgresql.JSONB, nullable=True
    )
    status: Mapped[Optional[str]] = mapped_column(s.String, nullable=True)
    check_link: Mapped[Optional[str]] = mapped_column(s.String, nullable=True)
    pr_comment_link: Mapped[Optional[str]] = mapped_column(s.String, nullable=True)

    @property
    def ready_to_run(self) -> bool:
        """Whether all the runs have finished and we're ready to analyze the results."""
        return self.benchmarkable.all_runs_with_publishable_benchmark_results_finished() and (
            not self.benchmarkable.baseline
            or self.benchmarkable.baseline.all_runs_with_publishable_benchmark_results_finished()
        )

    def run_benchalerts(self) -> None:
        """Ask Conbench v2 to publish the CI report, then mark this run as finished.

        This scheduler still owns Buildkite readiness and persistence. The comparison,
        GitHub Check, and PR comment are Conbench responsibilities in v2.
        """
        if self.reason.endswith("-wheel"):
            # No alerting on wheels for now.
            log.info(
                f"Skipping benchalerts for {self.benchmarkable_id} because it's a wheel"
            )
            self.mark_finished(report=None)
            return

        # For all other reasons, the benchmarkable ID is the commit hash
        commit_hash = self.benchmarkable_id

        # ...and the PR number should be populated, unless it's a merge-commit and
        # something went wrong finding the associated PR
        pr_number: Optional[int] = self.benchmarkable.pull_number
        if not pr_number:
            log.warning(f"Skipping benchalerts for {commit_hash}: no PR number found")
            self.mark_finished(report=None)
            return

        contender_runs = self.publishable_runs(self.benchmarkable)
        run_ids = [run.id for run in contender_runs]
        log.info(f"Analyzing run IDs: {run_ids}")
        if not run_ids:
            log.warning(f"Skipping benchalerts for {commit_hash}: no publishable runs")
            self.mark_finished(
                report={
                    "status": "skipped",
                    "status_reason": "no publishable benchmark runs",
                }
            )
            return

        possible_build_urls = [
            run.buildkite_build_web_url
            for run in contender_runs
            if run.buildkite_build_web_url
        ]
        log.info(
            f"Linking to the first in this list if it's nonempty: {possible_build_urls}"
        )
        build_url = possible_build_urls[0] if possible_build_urls else None

        cmd = self.conbench_ci_report_command(
            run_ids=run_ids,
            contender_runs=contender_runs,
            build_url=build_url,
        )
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            check=False,
        )
        if result.returncode not in [0, 1]:
            raise RuntimeError(
                "conbench ci report failed with exit code "
                f"{result.returncode}: {result.stderr or result.stdout}"
            )

        try:
            report = json.loads(result.stdout)
        except json.JSONDecodeError as e:
            raise RuntimeError(f"could not decode conbench ci report JSON: {e}") from e

        self.mark_finished(report=report)

    def conbench_ci_report_command(self, run_ids, contender_runs, build_url):
        if not Config.CONBENCH_URL:
            raise RuntimeError("CONBENCH_URL is required to publish Conbench reports")

        cmd = [
            os.getenv("CONBENCH_CLI", "conbench-v2"),
            "ci",
            "report",
            "--server",
            Config.CONBENCH_URL,
            "--repository",
            self.benchmarkable.repo,
            "--commit",
            self.benchmarkable_id,
            "--run-ids",
            ",".join(run_ids),
            "--github-check",
            "--github-pr-comment",
            "--github-pr-number",
            str(self.benchmarkable.pull_number),
            "--github-external-id",
            self.id,
        ]
        if build_url:
            cmd.extend(["--build-url", build_url])

        baseline_run_ids = self.baseline_run_ids(contender_runs)
        if baseline_run_ids:
            cmd.extend(["--baseline-run-ids", ",".join(baseline_run_ids)])
        elif self.reason == "pull-request":
            cmd.extend(["--baseline", "fork_point"])
        else:
            cmd.extend(["--baseline", "parent"])

        return cmd

    def baseline_run_ids(self, contender_runs):
        baseline = self.benchmarkable.baseline
        if not baseline:
            return []

        baseline_runs_by_machine = {
            run.machine_name: run.id for run in self.publishable_runs(baseline)
        }
        baseline_run_ids = []
        for run in contender_runs:
            baseline_run_id = baseline_runs_by_machine.get(run.machine_name)
            if not baseline_run_id:
                log.warning(
                    "No baseline run found for benchmarkable "
                    f"{self.benchmarkable_id} on machine {run.machine_name}; "
                    "falling back to Conbench baseline selection"
                )
                return []
            baseline_run_ids.append(baseline_run_id)

        return baseline_run_ids

    @staticmethod
    def publishable_runs(benchmarkable):
        return [
            run for run in benchmarkable.runs if run.machine.publish_benchmark_results
        ]

    def mark_finished(self, report: Optional[dict]) -> None:
        """Mark this run as finished, and save compact report metadata."""
        if report:
            self.status = report.get("status")
            self.output = {
                "finished": True,
                "status_reason": report.get("status_reason"),
                "summary": report.get("summary"),
            }
            report_url = report.get("report_url")
            if report_url:
                # Conbench v2 posts GitHub output itself. Store the report URL in the
                # old link fields so existing Buildkite and Slack surfaces keep working.
                self.check_link = report_url
                self.pr_comment_link = report_url

        self.finished_at = s.sql.func.now()
        self.save()
