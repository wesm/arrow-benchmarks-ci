## How to Add New Benchmark Machine for Running Apache Arrow Repo Benchmarks

##### 1. Create Pull Request to add your machine to `Config.MACHINES`
Adding new machine to `Config.MACHINES` and merging your pull request into `main` branch will automatically
- create **"Arrow BCI Benchmark on ..."** Buildkite pipeline for your machine in
[Apache Arrow CI Buildkite organization](https://buildkite.com/apache-arrow)
- enable **"Arrow BCI Benchmark on ..."** Buildkite pipeline builds being created for all
[Apache Arrow repo](https://github.com/apache/arrow) master commits and `@ursabot` benchmark requests on pull requests.

Add your benchmark machine to `MACHINES` in [config.py](../config.py) and set `publish_benchmark_results` to `False` so
benchmark results for your machine are not published to [Apache Arrow repo](https://github.com/apache/arrow) pull requests
until you are ready to do so.
```python
MACHINES = {
    "your-benchmark-machine": {
        "info": "Supported langs: Python",
        "default_filters": {
            "arrow-commit": {
                "langs": {
                    "Python": {
                        "names": [
                            "csv-read",
                            "dataframe-to-table",
                            "dataset-filter",
                            "dataset-read",
                            "dataset-select",
                            "dataset-selectivity",
                            "file-read",
                            "file-write",
                            "wide-dataframe",
                        ]
                    }
                }
            }
        },
        "supported_filters": ["name", "lang"],
        "publish_benchmark_results": False,
    },
}
```

##### 2. Get environment vars for Buildkite Agent on your benchmark machine
- Add a comment to your Pull Request
```
@ElenaHenderson Will you please provide environment vars for Buildkite Agent for our benchmark machine
with name = <your benchmark machine>:
- ARROW_BCI_URL
- ARROW_BCI_API_ACCESS_TOKEN
- BUILDKITE_AGENT_TOKEN
- BUILDKITE_QUEUE
- CONBENCH_TOKEN
- CONBENCH_URL
- MACHINE

Please use <your email address> to share the environment vars with us.
```
- Environment vars will be shared with you using LastPass

- Create GITHUB_PAT
    - Go to https://github.com/settings/tokens/new
    - enter Note
    - select `repo:status` and `public_repo` under Select scopes
    - click Generate token
    - copy token and use it as `GITHUB_PAT` in this doc


##### 3. Setup your benchmark machine
###### On Ubuntu
Note:
- [setup-benchmark-machine-ubuntu-20.04-for-apache-arrow-benchmarks.sh](../scripts/setup-benchmark-machine-ubuntu-20.04-for-apache-arrow-benchmarks.sh) only installs dependencies for Apache Arrow C++, Python, R, Java and JavaScript.
- If you need to install additional dependencies, please update [setup-benchmark-machine-ubuntu-20.04-for-apache-arrow-benchmarks.sh](../scripts/setup-benchmark-machine-ubuntu-20.04-for-apache-arrow-benchmarks.sh).
- If your machine is running OS other than Ubuntu, please create a new setup script and use [setup-benchmark-machine-ubuntu-20.04-for-apache-arrow-benchmarks.sh](../scripts/setup-benchmark-machine-ubuntu-20.04-for-apache-arrow-benchmarks.sh) as a reference.

```shell script
sudo su
cd ~

# Export env vars to be used by setup-benchmark-machine-ubuntu-20.04-for-apache-arrow-benchmarks.sh
export ARROW_BCI_URL=<ARROW_BCI_URL>
export ARROW_BCI_API_ACCESS_TOKEN=<ARROW_BCI_API_ACCESS_TOKEN>
export BUILDKITE_AGENT_TOKEN=<BUILDKITE_AGENT_TOKEN>
export BUILDKITE_QUEUE=<BUILDKITE_QUEUE>
export CONBENCH_TOKEN=<CONBENCH_TOKEN>
export CONBENCH_URL=<CONBENCH_URL>
export CONBENCH_CLI=${CONBENCH_CLI:-conbench-v2}
export MACHINE=<MACHINE>
export GITHUB_PAT=<GITHUB_PAT>

# Install Apache Arrow C++, Python, R, Java and JavaScript dependencies and Buildkite Agent
curl -LO https://raw.githubusercontent.com/arctosalliance/arrow-benchmarks-ci/main/scripts/setup-benchmark-machine-ubuntu-20.04-for-apache-arrow-benchmarks.sh
chmod +x setup-benchmark-machine-ubuntu-20.04-for-apache-arrow-benchmarks.sh
source ./setup-benchmark-machine-ubuntu-20.04-for-apache-arrow-benchmarks.sh

# Verify you have at least these versions of java, javac, mvn, node and yarn
$ java -version
openjdk version "1.8.0_292"
$ javac -version
javac 1.8.0_292
$ mvn -version
Apache Maven 3.6.3
$ node --version
v14.18.2
$ yarn --version
1.22.17

# Start Buildkite Agent
systemctl enable buildkite-agent && systemctl start buildkite-agent

# Verify Buildkite Agent is running
ps aux | grep buildkite
journalctl -f -u buildkite-agent
```

###### On macOS arm64:

```shell script
cd ~

# Export env vars to be used by setup-benchmark-machine-macos.sh
export ARROW_BCI_URL=<ARROW_BCI_URL>
export ARROW_BCI_API_ACCESS_TOKEN=<ARROW_BCI_API_ACCESS_TOKEN>
export BUILDKITE_AGENT_TOKEN=<BUILDKITE_AGENT_TOKEN>
export BUILDKITE_QUEUE=<BUILDKITE_QUEUE>
export CONBENCH_TOKEN=<CONBENCH_TOKEN>
export CONBENCH_URL=<CONBENCH_URL>
export CONBENCH_CLI=${CONBENCH_CLI:-conbench-v2}
export MACHINE=<MACHINE>
export GITHUB_PAT=<GITHUB_PAT>

# Install Apache Arrow C++ dependencies and Buildkite Agent
curl -LO https://raw.githubusercontent.com/arctosalliance/arrow-benchmarks-ci/main/scripts/setup-benchmark-machine-macos-for-apache-arrow-benchmarks.sh
chmod +x setup-benchmark-machine-macos-for-apache-arrow-benchmarks.sh
source ./setup-benchmark-machine-macos-for-apache-arrow-benchmarks.sh

# Set NOPASSWD for user which will be used to run buildkite-agent
echo "<user-for-buildkite-agent> ALL=(ALL) NOPASSWD:ALL" | sudo tee -a /etc/sudoers

# Verify you have at least these versions of java, javac, mvn, node and yarn
$ java -version
openjdk version "1.8.0_292"
$ javac -version
javac 1.8.0_292
$ mvn -version
Apache Maven 3.8.4
$ node --version
v15.14.0
$ yarn --version
1.22.17

# Start Buildkite Agent
brew services start buildkite/buildkite/buildkite-agent

# Verify Buildkite Agent is running
ps aux | grep buildkite
tail -f "$(brew --prefix)"/var/log/buildkite-agent.log
```

##### 4. Test benchmark build on your machine
- Note that running `create_conda_env_and_run_benchmarks` will take for 4-5 hours.
- Please make sure to run this script as a user who owns buildkite-agent process:
    - Ubuntu: buildkite-agent
    - MacOS: user who started buildkite-agent using `brew services start buildkite/buildkite/buildkite-agent`

```shell script
# Clone arrow-benchmarks-ci repo
su - buildkite-agent # or whatever user you used to start buildkite-agent on MacOS
bash
git clone https://github.com/arctosalliance/arrow-benchmarks-ci.git
cd arrow-benchmarks-ci/

# Export env vars
export ARROW_BCI_URL=<ARROW_BCI_URL>
export ARROW_BCI_API_ACCESS_TOKEN=<ARROW_BCI_API_ACCESS_TOKEN>
export CONBENCH_TOKEN=<CONBENCH_TOKEN>
export CONBENCH_URL=<CONBENCH_URL>
export CONBENCH_CLI=${CONBENCH_CLI:-conbench-v2}
export MACHINE=<MACHINE>
export GITHUB_PAT=<GITHUB_PAT>
export PYTHON_VERSION=3.8
export BENCHMARKABLE=<latest arrow commit>
export BENCHMARKABLE_TYPE=arrow-commit
export RUN_ID=<test-random-string>
export RUN_NAME="test"

source buildkite/benchmark/utils.sh create_conda_env_and_run_benchmarks
```

##### 5. Disable Swap, CPU Frequency Scaling, Hyper-Threading & CPU Frequency Boost on your benchmark machine
Disabling Swap, CPU frequency scaling, Hyper-Threading & Boost will reduce benchmark results variability.
Note that each machine might have its own way of disabling these features or have its own name for some of these features.

Here are docs on how to do this on `ThinkCentre` machines:
- [How to Disable CPU Frequency Scaling](../docs/how-to-disable-CPU-frequency-scaling.md)
- [How to Disable Hyper-Threading](../docs/how-to-disable-hyper-threading.md)
- [How to Disable Swap](../docs/how-to-disable-swap.md)
- [How to Disable CPU Frequency Boost](../docs/how-to-dsiable-boost.md)


##### 6. Get Pull Request reviewed and merged
Suggested Reviewers:
- [Elena Henderson](https://github.com/elenahenderson)
- [Jonathan Keane](https://github.com/jonkeane)

##### 7. Request Buildkite pipeline for your benchmark machine to be made public
- Add a comment to your Pull Request:
```
@ElenaHenderson Will you please make Buildkite pipeline for benchmark machine ... public?
```

##### 8. Verify benchmark builds on your machine are running as expected
- Go to [Apache Arrow CI Buildkite organization](https://buildkite.com/apache-arrow)
- Click on **"Arrow BCI Benchmark on ..."** Buildkite pipeline for your machine and
verify benchmark builds are running as expected

##### 9. Verify benchmark results from your machine are logged into Conbench
- Go to [Conbench](https://conbench.ursa.dev/)
- Enter your machine name into Search box
- Click on a few runs and verify that all benchmark results form your machine are logged

##### 10. Create Pull Request to enable `publish_benchmark_results` for your machine
- Update `MACHINES` in [config.py](../config.py) and set `publish_benchmark_results` to `True` for your machine
