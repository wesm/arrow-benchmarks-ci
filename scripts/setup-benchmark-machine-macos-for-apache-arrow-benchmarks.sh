#!/bin/bash

echo "-------Installing C++ dependencies"
curl -LO https://raw.githubusercontent.com/apache/arrow/master/cpp/Brewfile
brew update && brew install node && brew bundle --file=Brewfile

echo "-------Installing JavaScript dependencies"
curl -o- https://raw.githubusercontent.com/nvm-sh/nvm/v0.37.2/install.sh | bash
export NVM_DIR="$HOME/.nvm"
[ -s "$NVM_DIR/nvm.sh" ] && \. "$NVM_DIR/nvm.sh"  # This loads nvm
[ -s "$NVM_DIR/bash_completion" ] && \. "$NVM_DIR/bash_completion"  # This loads nvm bash_completion
nvm install v15
node --version
nvm cache clear
brew install yarn
yarn --version

echo "-------Installing Java dependencies"
brew install maven
brew tap adoptopenjdk/openjdk
brew update && brew install --cask adoptopenjdk8

echo "-------Installing Buildkite Agent"
brew install buildkite/buildkite/buildkite-agent

echo "-------Setting up Buildkite agent config and hooks"
sed -i '' "s/xxx/$BUILDKITE_AGENT_TOKEN/g" "$(brew --prefix)"/etc/buildkite-agent/buildkite-agent.cfg
echo "tags=\"queue=$BUILDKITE_QUEUE\"" >> "$(brew --prefix)"/etc/buildkite-agent/buildkite-agent.cfg

touch "$(brew --prefix)"/etc/buildkite-agent/hooks/environment
{
  echo "export ARROW_BCI_URL=$ARROW_BCI_URL"
  echo "export ARROW_BCI_API_ACCESS_TOKEN=$ARROW_BCI_API_ACCESS_TOKEN"
  echo "export CONBENCH_TOKEN=$CONBENCH_TOKEN"
  echo "export CONBENCH_URL=$CONBENCH_URL"
  echo "export CONBENCH_CLI=${CONBENCH_CLI:-conbench-v2}"
  echo "export MACHINE=$MACHINE"
  echo "export GITHUB_PAT=$GITHUB_PAT"
} >> "$(brew --prefix)"/etc/buildkite-agent/hooks/environment

cp "$(brew --prefix)"/etc/buildkite-agent/hooks/pre-command.sample "$(brew --prefix)"/etc/buildkite-agent/hooks/pre-command
echo "source  $HOME/.bash_profile" >> "$(brew --prefix)"/etc/buildkite-agent/hooks/pre-command

echo "-------Installing conda"
curl -LO https://repo.anaconda.com/miniconda/Miniconda3-latest-MacOSX-arm64.sh
bash Miniconda3-latest-MacOSX-arm64.sh -b -p "$HOME/miniconda3"
"$HOME/miniconda3/bin/conda" init bash
