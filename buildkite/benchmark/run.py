import json
import logging
import os
import subprocess
import tempfile
from abc import ABC, abstractmethod
from datetime import datetime
from pathlib import Path
from typing import List

import psutil
import requests

from utils import generate_uuid

from .run_utils import post_logs_to_arrow_bci, run_context

log = logging.getLogger(__name__)
log.setLevel(logging.DEBUG)

benchmark_langs = ["C++", "Python", "R", "JavaScript", "Rust"]
benchmarkable_id = os.getenv("BENCHMARKABLE")
run_id = os.getenv("RUN_ID")
run_name = os.getenv("RUN_NAME")
machine = os.getenv("MACHINE")
arrow_bci_url = os.getenv("ARROW_BCI_URL")
arrow_bci_api_access_token = os.getenv("ARROW_BCI_API_ACCESS_TOKEN")
build_dir = os.getcwd()
total_machine_memory = psutil.virtual_memory().total
logging.basicConfig(level=logging.DEBUG)

CONBENCH_RESULTS_SUBMIT_COMMAND = (
    'if [ -d "$CONBENCH_RESULTS_DIR" ] '
    "&& find \"$CONBENCH_RESULTS_DIR\" -maxdepth 1 -name '*.json' -print -quit "
    "| grep -q .; then "
    '"${CONBENCH_CLI:-conbench-v2}" results submit '
    '"$CONBENCH_RESULTS_DIR/*.json" --server "$CONBENCH_URL" '
    '--jobs "${CONBENCH_SUBMIT_JOBS:-16}"; '
    'else echo "No Conbench result payloads found in $CONBENCH_RESULTS_DIR"; '
    "exit 1; fi"
)

repos_with_benchmark_groups = [
    {
        "benchmarkable_type": "arrow-commit",
        "repo": "https://github.com/wesm/benchmarks.git",
        "root": "benchmarks",
        "branch": "v2-conbench-submit",
        "setup_commands": ["pip install -e ."],
        "path_to_benchmark_groups_list_json": "benchmarks/benchmarks.json",
        "url_for_benchmark_groups_list_json": "https://raw.githubusercontent.com/wesm/benchmarks/v2-conbench-submit/benchmarks.json",
        "submit_results": True,
        "setup_commands_for_lang_benchmarks": {  # These commands need to be defined as functions in buildkite/benchmark/utils.sh
            "C++": ["install_minio"],
            "Python": ["create_data_dir"],
            "R": [
                "build_arrow_r",
                "install_arrowbench",
                "create_data_dir",
            ],
            # "Java": ["build_arrow_java"],
            # "JavaScript": ["install_java_script_project_dependencies"],
        },
        "env_vars": {
            "PYTHONFAULTHANDLER": "1",  # makes it easy to debug segmentation faults
            "BENCHMARKS_DATA_DIR": f"{os.getenv('HOME')}/data",  # allows to avoid loading Python and R benchmarks input data from s3 for every build
            "ARROWBENCH_DATA_DIR": f"{os.getenv('HOME')}/data",  # allows to avoid loading R benchmarks input data from s3 for every build
            "ARROW_SRC": f"{build_dir}/arrow",  # required by Java Script benchmarks
        },
    },
    {
        "benchmarkable_type": "arrow-commit",
        "repo": "https://github.com/wesm/arrowbench.git",
        "root": "arrowbench",
        "branch": "v2-conbench-payloads",
        "setup_commands": [],
        "path_to_benchmark_groups_list_json": "arrowbench/inst/benchmarks.json",
        "url_for_benchmark_groups_list_json": "https://raw.githubusercontent.com/wesm/arrowbench/v2-conbench-payloads/inst/benchmarks.json",
        "submit_results": True,
        "setup_commands_for_lang_benchmarks": {  # These commands need to be defined as functions in buildkite/benchmark/utils.sh
            "R": [
                "build_arrow_r",
                "install_arrowbench",
                "create_data_dir",
            ],
        },
        "env_vars": {
            "ARROWBENCH_DATA_DIR": f"{os.getenv('HOME')}/data",  # allows to avoid loading R benchmarks input data from s3 for every build
        },
    },
    {
        "benchmarkable_type": "arrow-commit",
        "repo": "https://github.com/wesm/arrow-benchmarks-ci.git",
        "root": "arrow-benchmarks-ci/adapters",
        "branch": "v2-conbench-ci-report",
        "setup_commands": ["pip install -r requirements.txt"],
        "path_to_benchmark_groups_list_json": "arrow-benchmarks-ci/adapters/benchmarks.json",
        "url_for_benchmark_groups_list_json": "https://raw.githubusercontent.com/wesm/arrow-benchmarks-ci/v2-conbench-ci-report/adapters/benchmarks.json",
        "setup_commands_for_lang_benchmarks": {  # These commands need to be defined as functions in buildkite/benchmark/utils.sh
            "C++": [],
            "Python": ["create_data_dir"],
            "R": [
                "build_arrow_r",
                "install_arrowbench",
                "create_data_dir",
            ],
            # "Java": ["build_arrow_java"],
            "JavaScript": ["install_java_script_project_dependencies"],
        },
        "env_vars": {
            "ARROW_SRC": f"{build_dir}/arrow",  # required by Java Script benchmarks
        },
    },
    {
        "benchmarkable_type": "benchmarkable-repo-commit",
        "repo": "https://github.com/ElenaHenderson/benchmarkable-repo.git",
        "root": "benchmarkable-repo",
        "branch": "master",
        "setup_commands": [],
        "path_to_benchmark_groups_list_json": "benchmarkable-repo/benchmarks.json",
        "url_for_benchmark_groups_list_json": "https://raw.githubusercontent.com/ElenaHenderson/benchmarkable-repo/master/benchmarks.json",
        "setup_commands_for_lang_benchmarks": {},
        "env_vars": {},
    },
    # NOTE (EV): Temporarily commented these out because failing builds were getting created
    # for them even though they don't have any benchmarks
    #
    # {
    #     "benchmarkable_type": "arrow-rs-commit",
    #     "repo": "https://github.com/apache/arrow-rs.git",
    #     "root": "arrow-rs/conbench",
    #     "branch": "master",
    #     "setup_commands": ["pip install -r requirements.txt"],
    #     "path_to_benchmark_groups_list_json": "arrow-rs/conbench/benchmarks.json",
    #     "url_for_benchmark_groups_list_json": "https://raw.githubusercontent.com/apache/arrow-rs/master/conbench/benchmarks.json",
    #     "setup_commands_for_lang_benchmarks": {},
    #     "env_vars": {},
    # },
    # {
    #     "benchmarkable_type": "arrow-datafusion-commit",
    #     "repo": "https://github.com/apache/arrow-datafusion.git",
    #     "root": "arrow-datafusion/conbench",
    #     "branch": "master",
    #     "setup_commands": ["pip install -r requirements.txt"],
    #     "path_to_benchmark_groups_list_json": "arrow-datafusion/conbench/benchmarks.json",
    #     "url_for_benchmark_groups_list_json": "https://raw.githubusercontent.com/apache/arrow-datafusion/master/conbench/benchmarks.json",
    #     "setup_commands_for_lang_benchmarks": {},
    #     "env_vars": {},
    # },
]

retryable_benchmark_groups = [
    "csv-read",
    "dataframe-to-table",
    "dataset-read",
    "dataset-selectivity",
    "file-read",
    "file-write",
    "partitioned-dataset-filter",
]


class BenchmarkGroup:
    """
    Class representing a benchmark (i.e. code) that can be run with various sets of
    parameters.

    Parameters
    ----------
    runner : str
        A string specifying which runner to use. Current options are `"conbench"`,
        `"arrowbench"`, and `"adapters"`. The authoritative list is in
        `Run.run_all_benchmark_groups()`.
    lang : str
        Language of the benchmark as specified in filters in `config.py`. Usually
        capitalized, e.g. `"Python"`, `"R"`, or `"C++"`.
    name : str
        Name of the benchmark as used in benchmark repo metadata JSON and filters in
        `config.py`. May not correspond to internal benchmark name and
        `result.tags["name"]`.
    command : str
        Command used with runner to run the benchmark. From benchmark repo metadata JSON.
    options : str
        Additional options to be passed to runner. For `"conbench"` runner, `command` is
        split into `{name} {options}` on the first space. For other runners, `name` is
        specified separately and `options` is not used.
    flags : str
        Flags from benchmark repo metadata JSON. `language` is a required key; others
        like `cloud` are optional.
    mock_run : bool
        Is this a mock run that should not attempt to run anything or send results to
        Conbench?
    """

    def __init__(
        self,
        runner: str,
        lang: str,
        name: str,
        command: str,
        options: str = "",
        flags: str = "",
        mock_run: bool = False,
    ):
        self.id = generate_uuid()
        self.runner = runner
        self.lang = lang
        self.name = name
        self.base_command = command
        self.options = options
        self.flags = flags
        self.process_pid = psutil.Process().pid
        self.mock_run = mock_run
        self.memory_monitor = None
        self.started_at = None
        self.finished_at = None
        self.return_code = None
        self.stderr = None

    def __repr__(self):
        return f"<Benchmark {self.name} {self.lang}>"

    @property
    def command(self):
        if self.runner == "conbench":
            command = f'conbench {self.name} {self.options} --run-id=$RUN_ID --run-name="$RUN_NAME" --run-reason="$RUN_REASON"'

            if self.lang == "Java":
                command += f" --commit={benchmarkable_id} --src={build_dir}/arrow"
        elif self.runner == "arrowbench":
            # arrowbench benchmarks should be run together, not independently
            command = self.base_command
        elif self.runner == "adapter":
            # for adapters, command should be a shell command to run the file that calls it
            command = self.base_command
        else:
            raise NotImplementedError(
                f"No command available for runner `{self.runner}`!"
            )

        return command

    @property
    def failed(self):
        if self.return_code or self.stderr:
            return self.return_code != 0 or "ERROR" in self.stderr

        return False

    @property
    def total_run_time(self):
        if self.started_at and self.finished_at:
            return self.finished_at - self.started_at

    @property
    def retry_on_failure(self):
        return self.name in retryable_benchmark_groups

    def start_memory_monitor(self):
        if self.mock_run:
            return

        # Monitor memory only if memory usage can be logged to Arrow Benchmarks CI
        if not arrow_bci_url or not arrow_bci_api_access_token:
            return

        # Monitor memory only for Python and R benchmarks
        if self.lang not in ["Python", "R"]:
            return

        self.memory_monitor = subprocess.Popen(
            f"python -m buildkite.benchmark.monitor_memory {self.process_pid} {self.id}",
            shell=True,
            executable="/bin/bash",
        )

    def stop_memory_monitor(self):
        if self.mock_run:
            return

        if self.memory_monitor:
            self.memory_monitor.kill()
            self.memory_monitor = None

    def log_data(self):
        return {
            "type": "BenchmarkGroupExecution",
            "id": self.id,
            "lang": self.lang,
            "name": self.name,
            "options": self.options,
            "flags": self.flags,
            "benchmarkable_id": benchmarkable_id,
            "run_id": run_id,
            "run_name": run_name,
            "machine": machine,
            "process_pid": psutil.Process().pid,
            "command": self.command,
            "started_at": str(self.started_at) if self.started_at else None,
            "finished_at": str(self.finished_at) if self.finished_at else None,
            "total_run_time": str(self.total_run_time) if self.total_run_time else None,
            "failed": self.failed,
            "return_code": self.return_code,
            "stderr": self.stderr,
            "total_machine_virtual_memory": total_machine_memory,
        }

    def log_execution(self):
        if self.mock_run:
            return

        log.info(self.log_data())
        post_logs_to_arrow_bci("logs", self.log_data())


class CommandExecutor:
    def __init__(self) -> None:
        self.executed_commands = []

    def execute_command(
        self, command: str, path: str = ".", exit_on_failure: bool = True
    ):
        log.info(f"start child process: {command}")
        self.executed_commands.append((command, path, exit_on_failure))

        child = subprocess.run(
            f"cd {path}; {command}",
            capture_output=True,
            shell=True,
            executable="/bin/bash",
        )
        stderr = child.stderr.decode()
        stdout = child.stdout.decode()

        log.info(
            "child process exited with code %s.\nstderr:\n%s\n\nstdout:\n%s",
            child.returncode,
            stderr,
            stdout,
        )

        # Note(JP): better: rely only on exit code.
        if exit_on_failure and (child.returncode != 0 or "ERROR" in stderr):
            raise Exception("command failed, exit_on_failure set")

        # Always fail the build if benchmark logs have Internal Server Error because
        # it could mean that we are loosing benchmark results because
        # Conbench can't store benchmark results
        # Note(JP): better: improve child  process in terms of error handling,
        # then here rely only on exit code.
        if "Internal Server Error" in stdout or "Internal Server Error" in stderr:
            log.error(stdout)
            log.error(stderr)
            raise Exception(
                "Failed to post benchmark results because of Internal Server Error"
            )

        log.info(f"Done executing -> {command}")
        return child.returncode, stderr


class BenchmarkGroupsRunner(ABC):
    "Abstract class for runners capable of running a set of benchmarks"

    def __init__(self, root: str, executor: CommandExecutor) -> None:
        self.root = root
        self.executor = executor

    @abstractmethod
    def run_benchmark_groups(self, benchmark_groups: List[BenchmarkGroup]) -> None:
        "Run a list of benchmark groups"


class ConbenchBenchmarkGroupsRunner(BenchmarkGroupsRunner):
    "Runner class for conbench runner"

    def run_benchmark_groups(self, benchmark_groups: List[BenchmarkGroup]) -> None:
        Run.print_env_vars()
        for benchmark_group in benchmark_groups:
            self.run_benchmark_group(benchmark_group)
            if benchmark_group.failed and benchmark_group.retry_on_failure:
                print(f"Retrying {benchmark_group.command}")
                self.run_benchmark_group(benchmark_group)

    def run_benchmark_group(self, benchmark_group: BenchmarkGroup) -> None:
        benchmark_group.started_at = datetime.now()
        benchmark_group.log_execution()
        benchmark_group.start_memory_monitor()

        return_code, stderr = self.executor.execute_command(
            benchmark_group.command, path=self.root, exit_on_failure=False
        )

        benchmark_group.finished_at = datetime.now()
        benchmark_group.return_code = return_code
        benchmark_group.stderr = stderr
        benchmark_group.log_execution()
        benchmark_group.stop_memory_monitor()


class ArrowbenchBenchmarkGroupsRunner(BenchmarkGroupsRunner):
    "Runner class for arrowbench"

    def run_benchmark_groups(self, benchmark_groups: List[BenchmarkGroup]) -> None:
        Run.print_env_vars()

        # NOTE: `bm.command` is the raw arrowbench name; `bm.name` is f"arrowbench/{bm.command}"
        # to disambiguate from labs/benchmarks versions when filtering.
        bm_names = [bm.command for bm in benchmark_groups]
        r_command = f"""
        bm_df <- arrowbench::get_package_benchmarks()
        bm_names <- c({str(bm_names)[1:-1]})
        bm_df_filtered <- bm_df[bm_df$name %in% bm_names, ]

        # Benchmark names to run:
        print(bm_names)
        # Benchmark dataframe to run:
        print(bm_df_filtered)

        arrowbench::run(
            bm_df_filtered,
            n_iter = 3L,
            drop_caches = TRUE,
            publish = TRUE,
            run_name = '{os.getenv('RUN_NAME')}',
            run_reason = '{os.getenv('RUN_REASON')}'
        )
        """

        (_, tmp) = tempfile.mkstemp(suffix=".R")
        tmp = Path(tmp)
        with open(tmp, "w") as f:
            f.write(r_command)

        self.executor.execute_command(
            f"R --vanilla -f {tmp}",
            path=self.root,
            exit_on_failure=False,
        )

        # leave tempfile for validation if mock run
        if not all([bg.mock_run for bg in benchmark_groups]):
            tmp.unlink()


class AdapterBenchmarkGroupsRunner(ConbenchBenchmarkGroupsRunner):
    """
    Runner class for benchadapt adapters

    Presently an alias, as relevant differences are all handled via the
    command.
    """


class Run:
    def __init__(self, repo_params):
        self.repo = repo_params["repo"]
        self.root = repo_params["root"]
        self.branch = repo_params["branch"]
        self.setup_commands = repo_params["setup_commands"]
        self.path_to_benchmark_groups_list_json = repo_params[
            "path_to_benchmark_groups_list_json"
        ]
        self.url_for_benchmark_groups_list_json = repo_params[
            "url_for_benchmark_groups_list_json"
        ]
        self.benchmarkable_type = os.getenv("BENCHMARKABLE_TYPE")
        self.filters = json.loads(os.getenv("FILTERS", "{}"))
        self.setup_commands_for_lang_benchmarks = repo_params[
            "setup_commands_for_lang_benchmarks"
        ]
        self.env_vars = repo_params["env_vars"]
        self.submit_results = repo_params.get("submit_results", False)
        self.benchmark_groups = []
        self.executor = CommandExecutor()

    def capture_context(self):
        post_logs_to_arrow_bci(f"runs/{run_id}", run_context())

    def setup_benchmarks_repo(self):
        # if benchmarks are located in the same repo as was cloned in utils.sh, do not clone it again
        if os.getenv("REPO") == self.repo:
            return

        if not Path(self.root).exists():
            self.executor.execute_command(f"git clone {self.repo}")

        self.executor.execute_command(
            f"git fetch && git checkout {self.branch}", self.root
        )
        for command in self.setup_commands:
            self.executor.execute_command(command, self.root)

    def setup_conbench_credentials(self):
        with open(f"{build_dir}/{self.root}/.conbench", "w") as f:
            f.writelines(
                [
                    f"url: {os.getenv('CONBENCH_URL', '')}\n",
                    f"host_name: {os.getenv('MACHINE', '')}\n",
                ]
            )

    def set_benchmark_groups(self, mock_run=False):
        """
        Gets JSON from benchmarks repo and sets `.benchmark_groups` attribute
        to list of instances of `BenchmarkGroup`

        Schema for benchmarks repo JSON (where `Optional` denotes a field can
        be missing):

        ```
        [
            {
                "command": str,
                "name": Optional[str],
                "runner": Optional[str] = "conbench",
                "flags": {
                    "language": str,
                    ...
                }
            },
            ...
        ]
        ```

        If `name` is not specified, it is inferred to be the first
        space-delimited word in `command`. Specifying it directly allows more
        flexible command structure.
        """
        for benchmark_group in self.get_benchmark_groups():
            runner = benchmark_group.get("runner", "conbench")
            name = benchmark_group.get("name")
            options = ""
            command = benchmark_group["command"]
            if not name:
                name, options = (
                    command.split(" ", 1) if " " in command else (command, "")
                )

            self.benchmark_groups.append(
                BenchmarkGroup(
                    runner=runner,
                    lang=benchmark_group["flags"]["language"],
                    name=name,
                    command=command,
                    options=options,
                    flags=benchmark_group["flags"],
                    mock_run=mock_run,
                )
            )

    def get_benchmark_groups(self):
        with open(self.path_to_benchmark_groups_list_json) as f:
            return json.load(f)

    def filter_benchmark_groups(self):
        if not self.filters:
            return

        if "command" in self.filters:
            self.benchmark_groups = [
                BenchmarkGroup(
                    runner="conbench",
                    lang="C++",
                    name=self.filters["command"],
                    command=None,
                )
            ]
            return

        self.benchmark_groups = list(
            filter(
                lambda benchmark_group: benchmark_group.lang in self.filters["langs"]
                and benchmark_group.name
                in self.filters["langs"][benchmark_group.lang]["names"],
                self.benchmark_groups,
            )
        )

    def set_env_vars(self):
        default_env_vars = {
            "CONBENCH_MACHINE_INFO_NAME": os.getenv("MACHINE", ""),
            "CONBENCH_PROJECT_REPOSITORY": "https://github.com/apache/arrow",
            "CONBENCH_PROJECT_COMMIT": benchmarkable_id or "",
            "CONBENCH_PROJECT_PR_NUMBER": os.getenv("BENCHMARKABLE_PR_NUMBER", ""),
            "CONBENCH_RESULTS_DIR": str(
                Path(build_dir) / self.root / "bench-results" / (run_id or "local")
            ),
        }
        for var, value in default_env_vars.items():
            if value:
                os.environ[var] = value

        for var, value in self.env_vars.items():
            os.environ[var] = value

    def submit_conbench_results(self):
        self.executor.execute_command(
            CONBENCH_RESULTS_SUBMIT_COMMAND,
            exit_on_failure=True,
        )

    @staticmethod
    def print_env_vars():
        for var, value in sorted(os.environ.items()):
            if "PASSWORD" in var or "SECRET" in var or "TOKEN" in var or "PAT" in var:
                log.info(f"{var}=[REDACTED]")
            else:
                log.info(f"{var}={value}")

    def benchmark_groups_for_lang(self, lang):
        return list(
            filter(
                lambda benchmark_group: benchmark_group.lang == lang,
                self.benchmark_groups,
            )
        )

    def additional_setup_for_benchmark_groups(self, lang):
        for command in self.setup_commands_for_lang_benchmarks.get(lang, []):
            self.executor.execute_command(
                f"source buildkite/benchmark/utils.sh {command}"
            )

    def mark_benchmark_groups_failed(self, lang, stderr):
        for benchmark_group in self.benchmark_groups_for_lang(lang):
            benchmark_group.stderr = stderr
            benchmark_group.log_execution()

    def print_results(self):
        print(
            "======================= Benchmark Groups Results =========================="
        )
        for benchmark_group in filter(
            lambda b: b.failed is False, self.benchmark_groups
        ):
            print(
                "PASSED",
                benchmark_group.lang,
                benchmark_group.name,
                benchmark_group.total_run_time,
            )

        for benchmark_group in filter(lambda b: b.failed, self.benchmark_groups):
            print(
                "FAILED",
                benchmark_group.lang,
                benchmark_group.name,
                benchmark_group.return_code,
                benchmark_group.stderr[-200:-1] if benchmark_group.stderr else "",
            )

    def failed_benchmark_groups(self):
        return list(filter(lambda b: b.failed, self.benchmark_groups))

    def run_all_benchmark_groups(self):
        self.capture_context()
        self.setup_benchmarks_repo()
        self.setup_conbench_credentials()
        self.set_env_vars()
        self.set_benchmark_groups()
        self.filter_benchmark_groups()

        for lang in benchmark_langs:
            lang_benchmark_groups = self.benchmark_groups_for_lang(lang=lang)
            if not lang_benchmark_groups:
                continue

            if self.benchmarkable_type.endswith("-commit"):
                try:
                    self.additional_setup_for_benchmark_groups(lang)
                except Exception as e:
                    log.exception(e)
                    stderr = f"Setup for {lang} benchmark groups failed"
                    self.mark_benchmark_groups_failed(lang, stderr)
                    continue

            for runner in set([bg.runner for bg in lang_benchmark_groups]):
                runner_lang_benchmark_groups = filter(
                    lambda bg: bg.runner == runner,
                    lang_benchmark_groups,
                )
                runner_lookup = {
                    "conbench": ConbenchBenchmarkGroupsRunner,
                    "arrowbench": ArrowbenchBenchmarkGroupsRunner,
                    "adapter": AdapterBenchmarkGroupsRunner,
                }
                runner_cls = runner_lookup[runner]
                runner_instance = runner_cls(root=self.root, executor=self.executor)

                runner_instance.run_benchmark_groups(runner_lang_benchmark_groups)

        self.print_results()

        if self.submit_results and self.benchmark_groups:
            self.submit_conbench_results()

        if len(self.failed_benchmark_groups()) > 0:
            raise Exception("Build has failed benchmarks.")


class MockCommandExecutor(CommandExecutor):
    def execute_command(
        self, command: str, path: str = ".", exit_on_failure: bool = True
    ):
        log.info(f"Started executing -> {command}")
        self.executed_commands.append((command, path, exit_on_failure))
        return 0, ""


# MockRun is used for:
# 1. testing Run().run_all_benchmark_groups method in non-benchmark machine environment without executing any
# shell commands
# 2. checking if provided benchmark filters on PR benchmark request comments do not filter out all benchmarks in
# https://raw.githubusercontent.com/wesm/benchmarks/v2-conbench-submit/benchmarks.json
class MockRun(Run):
    def __init__(self, repo_params, filters):
        super().__init__(repo_params)
        self.filters = filters
        self.executor = MockCommandExecutor()

    def capture_context(self):
        pass

    def set_env_vars(self):
        pass

    def setup_conbench_credentials(self):
        pass

    def get_benchmark_groups(self):
        return requests.get(self.url_for_benchmark_groups_list_json).json()

    def set_benchmark_groups(self, mock_run=True):
        super().set_benchmark_groups(mock_run=mock_run)

    def has_benchmark_groups_to_execute(self):
        self.set_benchmark_groups()
        self.filter_benchmark_groups()
        return len(self.benchmark_groups) > 0
