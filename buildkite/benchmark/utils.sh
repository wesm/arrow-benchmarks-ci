#!/bin/bash

install_and_configure_sccache() {
  # sccache here is backed by an S3 bucket that only the EC2 benchmark agents
  # have IAM access to (and the released binary target is Linux-only). On macOS
  # skip it; the conda-forge `ccache` in the build env still gives local caching
  # that persists across builds.
  if [ "$(uname)" = "Darwin" ]; then
    echo "Skipping sccache setup on macOS"
    return 0
  fi

  # Install sccache using Arrow's install script
  local sccache_dir="$HOME/.local/bin"
  mkdir -p "$sccache_dir"
  pushd $REPO_DIR
  ci/scripts/install_sccache.sh unknown-linux-musl "$sccache_dir"
  popd
  export PATH="$sccache_dir:$PATH"

  # Configure sccache to use S3 with architecture-specific prefix
  # to prevent arm64 and x86_64 machines from overwriting each other's cache
  export SCCACHE_BUCKET="arrow-benchmarks-sccache"
  export SCCACHE_REGION="us-east-1"
  export SCCACHE_S3_KEY_PREFIX="$(uname -m)"

  # Start sccache server and show stats
  sccache --start-server || true
  sccache --show-stats
}

init_conda() {
  eval "$(command "$HOME/miniconda3/bin/conda" 'shell.bash' 'hook' 2> /dev/null)"
}

create_conda_env_for_arrow_commit() {
  pushd $REPO_DIR

  conda -V
  conda create -y -n "${BENCHMARKABLE_TYPE}" --solver libmamba -c conda-forge \
  --file ci/conda_env_unix.txt \
  --file ci/conda_env_cpp.txt \
  --file ci/conda_env_python.txt \
  compilers \
  python="${PYTHON_VERSION}" \
  pip \
  pandas \
  r

  source dev/conbench_envs/hooks.sh activate_conda_env_for_benchmark_build
  source dev/conbench_envs/hooks.sh install_arrow_python_dependencies
  source dev/conbench_envs/hooks.sh set_arrow_build_and_run_env_vars

  export RANLIB=`which $RANLIB`
  export AR=`which $AR`

  source dev/conbench_envs/hooks.sh build_arrow_cpp
  source dev/conbench_envs/hooks.sh build_arrow_python
  source dev/conbench_envs/hooks.sh install_archery
  popd
}

create_conda_env_for_pyarrow_apache_wheel() {
  conda create -y -n "${BENCHMARKABLE_TYPE}" -c conda-forge \
    python="${PYTHON_VERSION}" \
    pandas
  conda activate "${BENCHMARKABLE_TYPE}"
  pip install "${BENCHMARKABLE}"
}

create_conda_env_for_benchmarkable_repo_commit() {
  conda create -y -n "${BENCHMARKABLE_TYPE}" python="${PYTHON_VERSION}"
  conda activate "${BENCHMARKABLE_TYPE}"
}

create_conda_env_for_arrow_rs_commit() {
  conda create -y -n "${BENCHMARKABLE_TYPE}" -c conda-forge \
    python="3.9" \
    rust
  conda activate "${BENCHMARKABLE_TYPE}"
}

create_conda_env_for_arrow_datafusion_commit() {
  conda create -y -n "${BENCHMARKABLE_TYPE}" -c conda-forge \
    python="3.9" \
    rust
  conda activate "${BENCHMARKABLE_TYPE}"
}

clone_repo() {
  rm -rf arrow
  git clone "${REPO}"
  pushd $REPO_DIR
  git fetch -v --prune -- origin "${BENCHMARKABLE}"
  git checkout -f "${BENCHMARKABLE}"
  popd
}

build_arrow_r() {
  pushd $REPO_DIR
  source dev/conbench_envs/hooks.sh build_arrow_r
  popd
}

build_arrow_java() {
  conda install -y --solver libmamba -c conda-forge 'maven=3.9.6' 'openjdk=17'
  # arrow java gets built as part of archery
}

install_minio() {
  pushd $REPO_DIR
  ci/scripts/install_minio.sh latest ${ARROW_HOME}
  popd
}

install_arrowbench() {
  # do I need to cd into benchmarks dir?
  git clone https://github.com/wesm/arrowbench.git
  pushd arrowbench
  git checkout v2-conbench-payloads
  popd
  R -e "remotes::install_local('./arrowbench')"
}

install_java_script_project_dependencies() {
  conda install -y --solver libmamba -c conda-forge 'nodejs>=12.20'
  npm install -g yarn
  pushd $REPO_DIR
  source dev/conbench_envs/hooks.sh install_java_script_project_dependencies
  popd
}

create_data_dir() {
  mkdir -p "${BENCHMARKS_DATA_DIR}"
  mkdir -p "${BENCHMARKS_DATA_DIR}/temp"
}

ensure_conbench_cli() {
  export CONBENCH_CLI="${CONBENCH_CLI:-conbench-v2}"

  if command -v "$CONBENCH_CLI" >/dev/null 2>&1; then
    echo "Using Conbench CLI: $CONBENCH_CLI"
    return 0
  fi

  if [ -n "${CONBENCH_CLI_DOWNLOAD_URL:-}" ]; then
    local cli_target
    case "$CONBENCH_CLI" in
      */*)
        cli_target="$CONBENCH_CLI"
        ;;
      *)
        local cli_dir="${CONBENCH_CLI_INSTALL_DIR:-$HOME/.local/bin}"
        mkdir -p "$cli_dir"
        export PATH="$cli_dir:$PATH"
        cli_target="$cli_dir/$CONBENCH_CLI"
        ;;
    esac
    echo "Downloading Conbench CLI from CONBENCH_CLI_DOWNLOAD_URL"
    curl -fsSL "$CONBENCH_CLI_DOWNLOAD_URL" -o "$cli_target"
    chmod +x "$cli_target"
  elif [ -n "${CONBENCH_CLI_INSTALL_COMMAND:-}" ]; then
    echo "Installing Conbench CLI with CONBENCH_CLI_INSTALL_COMMAND"
    eval "$CONBENCH_CLI_INSTALL_COMMAND"
  fi

  if command -v "$CONBENCH_CLI" >/dev/null 2>&1; then
    echo "Using Conbench CLI: $CONBENCH_CLI"
    return 0
  fi

  echo "Conbench CLI '$CONBENCH_CLI' was not found. Set CONBENCH_CLI to an executable, CONBENCH_CLI_DOWNLOAD_URL to a raw binary URL, or CONBENCH_CLI_INSTALL_COMMAND to an install command." >&2
  return 1
}

check_conbench_submit_env() {
  local missing=0

  if [ -z "${CONBENCH_URL:-}" ]; then
    echo "CONBENCH_URL is required for Conbench v2 result submission." >&2
    missing=1
  fi
  if [ -z "${CONBENCH_TOKEN:-}" ]; then
    echo "CONBENCH_TOKEN is required for Conbench v2 result submission." >&2
    missing=1
  fi

  return "$missing"
}

test_pyarrow_is_built() {
  echo "------------>Testing pyarrow is built"
  python -c "import pyarrow; print(pyarrow.__version__)"
  echo "------------>End"
}

create_conda_env_and_run_benchmarks() {
  init_conda
  case "${BENCHMARKABLE_TYPE}" in
    "arrow-commit")
      export REPO=https://github.com/apache/arrow.git
      export REPO_DIR=arrow
      clone_repo
      install_and_configure_sccache
      # retry this sometimes-flaky step
      create_conda_env_for_arrow_commit || create_conda_env_for_arrow_commit
      test_pyarrow_is_built
      ;;
    "pyarrow-apache-wheel")
      create_conda_env_for_pyarrow_apache_wheel
      ;;
    "benchmarkable-repo-commit")
      export REPO=https://github.com/ElenaHenderson/benchmarkable-repo.git
      export REPO_DIR=benchmarkable-repo
      clone_repo
      create_conda_env_for_benchmarkable_repo_commit
      ;;
    "arrow-rs-commit")
      export REPO=https://github.com/apache/arrow-rs.git
      export REPO_DIR=arrow-rs
      clone_repo
      create_conda_env_for_arrow_rs_commit
      ;;
    "arrow-datafusion-commit")
      export REPO=https://github.com/apache/arrow-datafusion.git
      export REPO_DIR=arrow-datafusion
      clone_repo
      create_conda_env_for_arrow_datafusion_commit
      ;;
  esac

  # pypi doesn't have wheels for macos 13 and source build fails
  conda install -y --solver libmamba -c conda-forge 'psycopg2-binary'
  pip install -r requirements.txt
  ensure_conbench_cli
  check_conbench_submit_env
  python -m buildkite.benchmark.run_benchmark_groups
}

"$@"
