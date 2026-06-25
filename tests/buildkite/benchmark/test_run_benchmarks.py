import json
import os
import subprocess
import sys
from copy import deepcopy
from pathlib import Path

from buildkite.benchmark import run as benchmark_run
from buildkite.benchmark.run import (CONBENCH_RESULTS_SUBMIT_COMMAND, MockRun,
                                     Run, repos_with_benchmark_groups)
from tests.helpers import (filter_with_cpp_only_benchmarks,
                           filter_with_file_only_benchmarks,
                           filter_with_python_only_benchmarks,
                           filter_with_r_only_benchmarks, machine_configs)


def test_mock_adapter_writes_v2_payload_file(tmp_path, monkeypatch):
    monkeypatch.setenv("CONBENCH_RESULTS_DIR", str(tmp_path))
    monkeypatch.setenv("RUN_ID", "buildkite-run-1")
    monkeypatch.setenv("RUN_NAME", "Buildkite smoke")
    monkeypatch.setenv("RUN_REASON", "manual-smoke")
    monkeypatch.setenv("CONBENCH_MACHINE_INFO_NAME", "buildkite-smoke-host")
    monkeypatch.setenv("CONBENCH_PROJECT_REPOSITORY", "https://github.com/apache/arrow")
    monkeypatch.setenv(
        "CONBENCH_PROJECT_COMMIT",
        "1111111111111111111111111111111111111111",
    )
    monkeypatch.setenv("CONBENCH_PROJECT_PR_NUMBER", "48886")

    subprocess.run(
        [sys.executable, "mock-adapter.py"],
        cwd="adapters",
        check=True,
        capture_output=True,
        text=True,
    )

    payloads = list(tmp_path.glob("*.json"))
    assert len(payloads) == 1
    payload = json.loads(payloads[0].read_text())
    assert payload["run_id"] == "buildkite-run-1"
    assert payload["run_name"] == "Buildkite smoke"
    assert payload["run_reason"] == "manual-smoke"
    assert payload["machine_info"]["name"] == "buildkite-smoke-host"
    assert payload["stats"]["data"] == [1.1, 2.2, 3.3]
    assert payload["github"] == {
        "repository": "https://github.com/apache/arrow",
        "commit": "1111111111111111111111111111111111111111",
        "pr_number": 48886,
    }


def test_v2_submit_command_metrics_smoke(tmp_path):
    results_dir = tmp_path / "bench-results"
    results_dir.mkdir()
    (results_dir / "one.json").write_text("{}\n")
    (results_dir / "two.json").write_text('{"x":1}\n')

    fake_bin = tmp_path / "bin"
    fake_bin.mkdir()
    conbench = fake_bin / "conbench-v2"
    conbench.write_text(
        "#!/bin/sh\n"
        "printf '%s\\n' "
        "'{\"ok\":true,\"id\":\"one\"}' "
        "'{\"ok\":true,\"id\":\"two\"}'\n"
    )
    conbench.chmod(0o700)

    env = {
        **os.environ,
        "CONBENCH_RESULTS_DIR": str(results_dir),
        "CONBENCH_URL": "http://conbench.example",
        "PATH": f"{fake_bin}:{os.environ['PATH']}",
    }

    result = subprocess.run(
        ["bash", "-c", CONBENCH_RESULTS_SUBMIT_COMMAND],
        cwd=tmp_path,
        check=False,
        capture_output=True,
        text=True,
        env=env,
    )

    assert result.returncode == 0
    assert "Conbench payload files: 2" in result.stdout
    assert "Conbench payload bytes: 11" in result.stdout
    assert "Conbench submit rows: 2" in result.stdout
    assert "Conbench submit seconds:" in result.stdout
    assert (tmp_path / "conbench-submit.jsonl").read_text().splitlines() == [
        '{"ok":true,"id":"one"}',
        '{"ok":true,"id":"two"}',
    ]


def test_local_v2_adapter_smoke_script_submits_payload(tmp_path):
    fake_bin = tmp_path / "bin"
    fake_bin.mkdir()
    args_file = tmp_path / "conbench-args.txt"
    python_marker = tmp_path / "python-wrapper-used"
    python_wrapper = fake_bin / "python-wrapper"
    python_wrapper.write_text(
        "#!/bin/sh\n"
        f"touch {python_marker}\n"
        f"exec {sys.executable} \"$@\"\n"
    )
    python_wrapper.chmod(0o700)
    conbench = fake_bin / "conbench-v2"
    conbench.write_text(
        "#!/bin/sh\n"
        "printf '%s\\n' \"$@\" > \"$FAKE_CONBENCH_ARGS\"\n"
        "printf '%s\\n' '{\"ok\":true,\"id\":\"adapter-smoke\"}'\n"
    )
    conbench.chmod(0o700)

    results_dir = tmp_path / "bench-results"
    submit_out = tmp_path / "conbench-submit.jsonl"
    env = {
        **os.environ,
        "CONBENCH_CLI": "conbench-v2",
        "CONBENCH_URL": "http://conbench.example",
        "CONBENCH_TOKEN": "dummy-token",
        "CONBENCH_RESULTS_DIR": str(results_dir),
        "CONBENCH_SUBMIT_OUT": str(submit_out),
        "CONBENCH_SUBMIT_JOBS": "7",
        "FAKE_CONBENCH_ARGS": str(args_file),
        "PATH": f"{fake_bin}:{os.environ['PATH']}",
        "PYTHON": str(python_wrapper),
        "RUN_ID": "adapter-smoke-run",
        "RUN_NAME": "adapter smoke run",
        "RUN_REASON": "manual-smoke",
        "CONBENCH_PROJECT_COMMIT": "1111111111111111111111111111111111111111",
    }

    result = subprocess.run(
        ["bash", "scripts/conbench-v2-adapter-smoke.sh"],
        check=False,
        capture_output=True,
        text=True,
        env=env,
    )

    assert result.returncode == 0, result.stderr
    assert "Conbench v2 adapter smoke payloads:" in result.stdout
    payloads = list(results_dir.glob("*.json"))
    assert len(payloads) == 1
    assert json.loads(payloads[0].read_text())["run_id"] == "adapter-smoke-run"
    assert python_marker.exists()
    assert submit_out.read_text().splitlines() == ['{"ok":true,"id":"adapter-smoke"}']
    assert args_file.read_text().splitlines() == [
        "results",
        "submit",
        f"{results_dir}/*.json",
        "--server",
        "http://conbench.example",
        "--jobs",
        "7",
    ]


def test_conbench_metadata_file_does_not_store_legacy_auth(tmp_path, monkeypatch):
    repo_root = tmp_path / "benchmarks"
    repo_root.mkdir()
    monkeypatch.setattr(benchmark_run, "build_dir", str(tmp_path))
    monkeypatch.setenv("CONBENCH_URL", "https://conbench-v2.example")
    monkeypatch.setenv("MACHINE", "buildkite-linux")

    runner = Run(
        {
            "repo": "https://github.com/wesm/benchmarks.git",
            "root": "benchmarks",
            "branch": "v2-conbench-submit",
            "setup_commands": [],
            "path_to_benchmark_groups_list_json": "benchmarks.json",
            "url_for_benchmark_groups_list_json": "https://example.invalid/benchmarks.json",
            "setup_commands_for_lang_benchmarks": {},
            "env_vars": {},
        }
    )

    runner.setup_conbench_metadata()

    metadata = (repo_root / ".conbench").read_text()
    assert metadata == (
        "url: https://conbench-v2.example\n"
        "host_name: buildkite-linux\n"
    )
    assert "email" not in metadata
    assert "password" not in metadata
    assert "token" not in metadata


def test_ensure_conbench_cli_accepts_existing_cli(tmp_path):
    cli = tmp_path / "conbench-v2"
    cli.write_text("#!/bin/sh\nexit 0\n")
    cli.chmod(0o700)
    env = {
        **os.environ,
        "CONBENCH_CLI": "conbench-v2",
        "PATH": f"{tmp_path}:{os.environ['PATH']}",
    }

    result = subprocess.run(
        ["bash", "buildkite/benchmark/utils.sh", "ensure_conbench_cli"],
        check=False,
        capture_output=True,
        text=True,
        env=env,
    )

    assert result.returncode == 0
    assert "Using Conbench CLI: conbench-v2" in result.stdout


def test_ensure_conbench_cli_runs_install_command(tmp_path):
    install_dir = tmp_path / "bin"
    install_command = (
        f"mkdir -p {install_dir} && "
        f"printf '#!/bin/sh\\nexit 0\\n' > {install_dir}/conbench-v2 && "
        f"chmod +x {install_dir}/conbench-v2"
    )
    env = {
        **os.environ,
        "CONBENCH_CLI": "conbench-v2",
        "CONBENCH_CLI_INSTALL_COMMAND": install_command,
        "PATH": f"{install_dir}:{os.environ['PATH']}",
    }

    result = subprocess.run(
        ["bash", "buildkite/benchmark/utils.sh", "ensure_conbench_cli"],
        check=False,
        capture_output=True,
        text=True,
        env=env,
    )

    assert result.returncode == 0
    assert "Installing Conbench CLI with CONBENCH_CLI_INSTALL_COMMAND" in result.stdout
    assert "Using Conbench CLI: conbench-v2" in result.stdout


def test_check_conbench_submit_env_requires_endpoint_and_token():
    env = {
        **os.environ,
        "CONBENCH_URL": "",
        "CONBENCH_TOKEN": "",
    }

    result = subprocess.run(
        ["bash", "buildkite/benchmark/utils.sh", "check_conbench_submit_env"],
        check=False,
        capture_output=True,
        text=True,
        env=env,
    )

    assert result.returncode == 1
    assert "CONBENCH_URL is required" in result.stderr
    assert "CONBENCH_TOKEN is required" in result.stderr


expected_setup_commands = [
    ("git clone https://github.com/wesm/benchmarks.git", ".", True),
    ("git fetch && git checkout v2-conbench-submit", "benchmarks", True),
    ("pip install -e .", "benchmarks", True),
]

expected_submit_command = [
    (
        CONBENCH_RESULTS_SUBMIT_COMMAND,
        ".",
        True,
    )
]

expected_setup_commands_for_cpp_benchmarks = [
    ("source buildkite/benchmark/utils.sh install_minio", ".", True),
]

expected_setup_commands_for_r_benchmarks = [
    ("source buildkite/benchmark/utils.sh build_arrow_r", ".", True),
    ("source buildkite/benchmark/utils.sh install_arrowbench", ".", True),
    ("source buildkite/benchmark/utils.sh create_data_dir", ".", True),
]

expected_setup_commands_for_python_benchmarks = [
    ("source buildkite/benchmark/utils.sh create_data_dir", ".", True)
]


expected_commands_for_python_benchmarks = expected_setup_commands_for_python_benchmarks + [
    (
        'conbench csv-read ALL --iterations=3 --drop-caches=true --run-id=$RUN_ID --run-name="$RUN_NAME" --run-reason="$RUN_REASON"',
        "benchmarks",
        False,
    ),
    (
        'conbench dataframe-to-table ALL --iterations=3 --drop-caches=true --run-id=$RUN_ID --run-name="$RUN_NAME" --run-reason="$RUN_REASON"',
        "benchmarks",
        False,
    ),
    (
        'conbench dataset-filter ALL --iterations=3 --drop-caches=true --run-id=$RUN_ID --run-name="$RUN_NAME" --run-reason="$RUN_REASON"',
        "benchmarks",
        False,
    ),
    (
        'conbench dataset-read ALL --iterations=1 --all=true --drop-caches=true --run-id=$RUN_ID --run-name="$RUN_NAME" --run-reason="$RUN_REASON"',
        "benchmarks",
        False,
    ),
    (
        'conbench dataset-select ALL --iterations=3 --drop-caches=true --run-id=$RUN_ID --run-name="$RUN_NAME" --run-reason="$RUN_REASON"',
        "benchmarks",
        False,
    ),
    (
        'conbench dataset-selectivity ALL --iterations=3 --all=true --drop-caches=true --run-id=$RUN_ID --run-name="$RUN_NAME" --run-reason="$RUN_REASON"',
        "benchmarks",
        False,
    ),
    (
        'conbench file-read ALL --iterations=3 --all=true --drop-caches=true --run-id=$RUN_ID --run-name="$RUN_NAME" --run-reason="$RUN_REASON"',
        "benchmarks",
        False,
    ),
    (
        'conbench file-write ALL --iterations=3 --all=true --drop-caches=true --run-id=$RUN_ID --run-name="$RUN_NAME" --run-reason="$RUN_REASON"',
        "benchmarks",
        False,
    ),
    (
        'conbench wide-dataframe --iterations=3 --all=true --drop-caches=true --run-id=$RUN_ID --run-name="$RUN_NAME" --run-reason="$RUN_REASON"',
        "benchmarks",
        False,
    ),
]

expected_commands_for_r_benchmarks = expected_setup_commands_for_r_benchmarks + [
    (
        'conbench dataframe-to-table ALL --iterations=3 --drop-caches=true --language=R --run-id=$RUN_ID --run-name="$RUN_NAME" --run-reason="$RUN_REASON"',
        "benchmarks",
        False,
    ),
    (
        'conbench file-read ALL --iterations=3 --all=true --drop-caches=true --language=R --run-id=$RUN_ID --run-name="$RUN_NAME" --run-reason="$RUN_REASON"',
        "benchmarks",
        False,
    ),
    (
        'conbench file-write ALL --iterations=3 --all=true --drop-caches=true --language=R --run-id=$RUN_ID --run-name="$RUN_NAME" --run-reason="$RUN_REASON"',
        "benchmarks",
        False,
    ),
    (
        'conbench partitioned-dataset-filter --iterations=3 --all=true --drop-caches=true --run-id=$RUN_ID --run-name="$RUN_NAME" --run-reason="$RUN_REASON"',
        "benchmarks",
        False,
    ),
]

expected_commands_for_cpp_benchmarks = expected_setup_commands_for_cpp_benchmarks + [
    (
        'conbench cpp-micro --iterations=1 --run-id=$RUN_ID --run-name="$RUN_NAME" --run-reason="$RUN_REASON"',
        "benchmarks",
        False,
    ),
]

expected_commands_for_cpp_benchmarks_with_one_command_only = expected_setup_commands_for_cpp_benchmarks + [
    (
        'conbench cpp-micro --suite-filter=arrow-compute-vector-selection-benchmark --benchmark-filter=TakeStringRandomIndicesWithNulls/262144/2 --iterations=3  --run-id=$RUN_ID --run-name="$RUN_NAME" --run-reason="$RUN_REASON"',
        "benchmarks",
        False,
    ),
]


tests = [
    {
        "run_filters": {},
        "expected_commands": expected_setup_commands
        + expected_commands_for_cpp_benchmarks
        + expected_commands_for_python_benchmarks
        + expected_commands_for_r_benchmarks
        + expected_submit_command,
    },
    {
        "run_filters": filter_with_python_only_benchmarks,
        "expected_commands": expected_setup_commands
        + expected_commands_for_python_benchmarks
        + expected_submit_command,
    },
    {
        "run_filters": filter_with_r_only_benchmarks,
        "expected_commands": expected_setup_commands
        + expected_commands_for_r_benchmarks
        + expected_submit_command,
    },
    {
        "run_filters": filter_with_cpp_only_benchmarks,
        "expected_commands": expected_setup_commands
        + expected_commands_for_cpp_benchmarks
        + expected_submit_command,
    },
    {
        "run_filters": {"langs": {"Python": {"names": ["dataset-read"]}}},
        "expected_commands": expected_setup_commands
        + expected_setup_commands_for_python_benchmarks
        + [
            (
                'conbench dataset-read ALL --iterations=1 --all=true --drop-caches=true --run-id=$RUN_ID --run-name="$RUN_NAME" --run-reason="$RUN_REASON"',
                "benchmarks",
                False,
            ),
        ]
        + expected_submit_command,
    },
    {
        "run_filters": filter_with_file_only_benchmarks,
        "expected_commands": expected_setup_commands
        + expected_setup_commands_for_python_benchmarks
        + [
            (
                'conbench file-read ALL --iterations=3 --all=true --drop-caches=true --run-id=$RUN_ID --run-name="$RUN_NAME" --run-reason="$RUN_REASON"',
                "benchmarks",
                False,
            ),
            (
                'conbench file-write ALL --iterations=3 --all=true --drop-caches=true --run-id=$RUN_ID --run-name="$RUN_NAME" --run-reason="$RUN_REASON"',
                "benchmarks",
                False,
            ),
        ]
        + expected_setup_commands_for_r_benchmarks
        + [
            (
                'conbench file-read ALL --iterations=3 --all=true --drop-caches=true --language=R --run-id=$RUN_ID --run-name="$RUN_NAME" --run-reason="$RUN_REASON"',
                "benchmarks",
                False,
            ),
            (
                'conbench file-write ALL --iterations=3 --all=true --drop-caches=true --language=R --run-id=$RUN_ID --run-name="$RUN_NAME" --run-reason="$RUN_REASON"',
                "benchmarks",
                False,
            ),
        ]
        + expected_submit_command,
    },
    {
        "run_filters": {
            "command": "cpp-micro --suite-filter=arrow-compute-vector-selection-benchmark --benchmark-filter=TakeStringRandomIndicesWithNulls/262144/2 --iterations=3"
        },
        "expected_commands": expected_setup_commands
        + expected_commands_for_cpp_benchmarks_with_one_command_only
        + expected_submit_command,
    },
    {
        "run_filters": machine_configs["ursa-i9-9960x"]["default_filters"][
            "arrow-commit"
        ],
        "expected_commands": expected_setup_commands
        + expected_commands_for_python_benchmarks
        + expected_commands_for_r_benchmarks
        + expected_submit_command,
    },
]


def test_run_benchmarks():
    repo = [
        deepcopy(x)
        for x in repos_with_benchmark_groups
        if x["repo"].endswith("wesm/benchmarks.git")
    ][0]
    # These tests should use benchmarks.json in benchmarks repo but should not be affected any new benchmarks
    # that added since 2b217db086260ab3bb243e26253b7c1de0180777
    repo["url_for_benchmark_groups_list_json"] = (
        "https://raw.githubusercontent.com/arctosalliance/benchmarks/2b217db086260ab3bb243e26253b7c1de0180777/benchmarks.json"
    )
    for test in tests:
        print(test)
        run = MockRun(repo, test["run_filters"])
        run.benchmarkable_type = "arrow-commit"
        run.run_all_benchmark_groups()
        assert run.executor.executed_commands == test["expected_commands"]


def test_run_arrowbench_benchmarks(monkeypatch):
    run_id = "fake-run-id"
    run_name = "test-run-name"
    run_reason = "test"
    monkeypatch.setenv("RUN_ID", run_id)
    monkeypatch.setenv("RUN_NAME", run_name)
    monkeypatch.setenv("RUN_REASON", run_reason)

    repo = [
        deepcopy(x)
        for x in repos_with_benchmark_groups
        if x["repo"].endswith("wesm/arrowbench.git")
    ][0]
    # These tests should use benchmarks.json in arrowbench repo but should not be affected any new benchmarks
    # that added since c5e5af241f17d27aadc01548f283a2a977151b91
    repo["url_for_benchmark_groups_list_json"] = (
        "https://raw.githubusercontent.com/arctosalliance/arrowbench/c5e5af241f17d27aadc01548f283a2a977151b91/inst/benchmarks.json"
    )

    filter_with_arrowbench_r_only_benchmarks = deepcopy(filter_with_r_only_benchmarks)
    filter_with_arrowbench_r_only_benchmarks["langs"]["R"]["names"] = [
        "arrowbench/" + name
        for name in filter_with_arrowbench_r_only_benchmarks["langs"]["R"]["names"]
    ]

    expected_setup_commands = (
        [
            ("git clone https://github.com/wesm/arrowbench.git", ".", True),
            ("git fetch && git checkout v2-conbench-payloads", "arrowbench", True),
        ]
        + expected_setup_commands_for_r_benchmarks
    )

    run = MockRun(repo, filters=filter_with_arrowbench_r_only_benchmarks)
    run.benchmarkable_type = "arrow-commit"
    run.run_all_benchmark_groups()
    assert run.executor.executed_commands[: len(expected_setup_commands)] == expected_setup_commands
    run_command = run.executor.executed_commands[len(expected_setup_commands)]
    assert run.executor.executed_commands[-1:] == expected_submit_command
    # runs an ephemeral tempfile
    assert run_command[0].startswith("R --vanilla -f ")
    assert run_command[0].endswith(".R")
    assert run_command[1] == "arrowbench"
    assert run_command[2] is False
    tempfile_path = Path(run_command[0].split()[-1]).resolve()
    with open(tempfile_path, "r") as f:
        tempfile_lines = [line.strip() for line in f.readlines()]

    assert tempfile_lines == [
        "",
        "bm_df <- arrowbench::get_package_benchmarks()",
        "bm_names <- c('file-write', 'dataframe-to-table', "
        "'partitioned-dataset-filter', 'file-read')",
        "bm_df_filtered <- bm_df[bm_df$name %in% bm_names, ]",
        "",
        "# Benchmark names to run:",
        "print(bm_names)",
        "# Benchmark dataframe to run:",
        "print(bm_df_filtered)",
        "",
        "arrowbench::run(",
        "bm_df_filtered,",
        "n_iter = 3L,",
        "drop_caches = TRUE,",
        "publish = TRUE,",
        f"run_id = '{run_id}',",
        f"run_name = '{run_name}',",
        f"run_reason = '{run_reason}'",
        ")",
        "",
    ]

    tempfile_path.unlink()


def test_run_adapter_benchmarks():
    repo = [
        deepcopy(x)
        for x in repos_with_benchmark_groups
        if x["repo"].endswith("wesm/arrow-benchmarks-ci.git")
    ][0]
    # These tests should use benchmarks.json in arrow-benchmarks-ci repo but should not be affected any new benchmarks
    # that added since 1ca33e8800a11624faf89a85af817ca83e473f56
    repo["url_for_benchmark_groups_list_json"] = (
        "https://raw.githubusercontent.com/arctosalliance/arrow-benchmarks-ci/1ca33e8800a11624faf89a85af817ca83e473f56/adapters/benchmarks.json"
    )

    filters = {
        "langs": {
            "Python": {
                "names": [
                    "adapters/mock-adapter",
                ]
            }
        }
    }

    expected_setup_commands = [
        (
            "git clone https://github.com/wesm/arrow-benchmarks-ci.git",
            ".",
            True,
        ),
        (
            "git fetch && git checkout v2-conbench-ci-report",
            "arrow-benchmarks-ci/adapters",
            True,
        ),
        ("pip install -r requirements.txt", "arrow-benchmarks-ci/adapters", True),
        ("source buildkite/benchmark/utils.sh create_data_dir", ".", True),
    ]

    expected_run_commands = [
        ("python mock-adapter.py", "arrow-benchmarks-ci/adapters", False)
    ]

    run = MockRun(repo, filters=filters)
    run.benchmarkable_type = "arrow-commit"
    run.run_all_benchmark_groups()
    assert (
        run.executor.executed_commands
        == expected_setup_commands + expected_run_commands + expected_submit_command
    )
