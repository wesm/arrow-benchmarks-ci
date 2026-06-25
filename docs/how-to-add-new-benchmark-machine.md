## How to Add New Benchmark Machine

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


##### 3. Setup Buildkite Agent and Conda on your benchmark machine
Example of how Buildkite Agent should be setup and Conda could be setup on Ubuntu

```shell script
sudo su
cd ~

# Export env vars
export ARROW_BCI_URL=<ARROW_BCI_URL>
export ARROW_BCI_API_ACCESS_TOKEN=<ARROW_BCI_API_ACCESS_TOKEN>
export BUILDKITE_AGENT_TOKEN=<BUILDKITE_AGENT_TOKEN>
export BUILDKITE_QUEUE=<BUILDKITE_QUEUE>
export CONBENCH_TOKEN=<CONBENCH_TOKEN>
export CONBENCH_URL=<CONBENCH_URL>
export CONBENCH_CLI=${CONBENCH_CLI:-conbench-v2}
export MACHINE=<MACHINE>
export GITHUB_PAT=<GITHUB_PAT>

# Install Buildkite Agent
sh -c 'echo deb https://apt.buildkite.com/buildkite-agent stable main > /etc/apt/sources.list.d/buildkite-agent.list'
apt-key adv --keyserver hkp://keyserver.ubuntu.com:80 --recv-keys 32A37959C2FA5C3C99EFBC32A79206696452D198
apt-get update && sudo apt-get install -y buildkite-agent

# Set up Buildkite agent config and hooks
sed -i "s/xxx/$BUILDKITE_AGENT_TOKEN/g" /etc/buildkite-agent/buildkite-agent.cfg
echo "tags=\"queue=$BUILDKITE_QUEUE\"" >>/etc/buildkite-agent/buildkite-agent.cfg

touch /etc/buildkite-agent/hooks/environment
{
  echo "export ARROW_BCI_URL=$ARROW_BCI_URL"
  echo "export ARROW_BCI_API_ACCESS_TOKEN=$ARROW_BCI_API_ACCESS_TOKEN"
  echo "export CONBENCH_TOKEN=$CONBENCH_TOKEN"
  echo "export CONBENCH_URL=$CONBENCH_URL"
  echo "export CONBENCH_CLI=$CONBENCH_CLI"
  echo "export MACHINE=$MACHINE"
  echo "export GITHUB_PAT=$GITHUB_PAT"
} >> /etc/buildkite-agent/hooks/environment

cp /etc/buildkite-agent/hooks/pre-command.sample /etc/buildkite-agent/hooks/pre-command
echo "source /var/lib/buildkite-agent/.bashrc" >> /etc/buildkite-agent/hooks/pre-command

# Set NOPASSWD for buildkite-agent user
echo "buildkite-agent ALL=(ALL) NOPASSWD:ALL" | sudo tee -a /etc/sudoers

# Install conda
case $( uname -m ) in
  aarch64)
    conda_installer=Miniconda3-latest-Linux-aarch64.sh;;
  *)
    conda_installer=Miniconda3-latest-Linux-x86_64.sh;;
esac
curl -LO https://repo.anaconda.com/miniconda/$conda_installer
bash $conda_installer -b -p "/var/lib/buildkite-agent/miniconda3"
su - buildkite-agent -c "/var/lib/buildkite-agent/miniconda3/bin/conda init bash"

# Start Buildkite Agent
systemctl enable buildkite-agent && systemctl start buildkite-agent

# Verify Buildkite Agent is running
ps aux | grep buildkite
journalctl -f -u buildkite-agent
```


##### 4. Get Pull Request reviewed and merged
Suggested Reviewers:
- [Elena Henderson](https://github.com/elenahenderson)
- [Jonathan Keane](https://github.com/jonkeane)

##### 5. Request Buildkite pipeline for your benchmark machine to be made public
- Add a comment to your Pull Request:
```
@ElenaHenderson Will you please make Buildkite pipeline for benchmark machine ... public?
```

Once Pull Request is merged and pipeline is made public, you will be able
to see Buildkite pipeline for your machine on https://buildkite.com/apache-arrow

##### 6. Verify benchmark builds on your machine are running as expected
- Go to [Apache Arrow CI Buildkite organization](https://buildkite.com/apache-arrow)
- Click on **"Arrow BCI Benchmark on ..."** Buildkite pipeline for your machine and
verify benchmark builds are running as expected

##### 7. Verify benchmark results from your machine are logged into Conbench
- Go to [Conbench](https://conbench.ursa.dev/)
- Enter your machine name into Search box
- Click on a few runs and verify that all benchmark results form your machine are logged
