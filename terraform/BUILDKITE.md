# Buildkite Agent Configuration for Arrow Benchmarks

This document describes how to set up and use Buildkite agents for running Arrow benchmarks.

## Overview

The Terraform configuration creates three types of Buildkite agent stacks:

1. **arm64-t4g-2xlarge-linux** - ARM64 agents on T4g.2xlarge instances
2. **amd64-m5-4xlarge-linux** - AMD64 agents on M5.4xlarge instances
3. **amd64-c6a-4xlarge-linux** - AMD64 compute-optimized agents on C6a.4xlarge instances

Each stack:
- Uses AWS CloudFormation with the official Buildkite AWS Stack template
- Auto-scales from 0 to 4 instances based on build queue
- Uses 100% on-demand instances (no spot instances)
- Has a dedicated queue name matching the machine type
- Runs a bootstrap script to install dependencies

## Prerequisites

Before deploying, you need:

1. **Buildkite API Token** (for Terraform to manage pipelines and agent tokens)
   - Go to: https://buildkite.com/user/api-access-tokens/new
   - Required scopes:
     - `graphql` (required for creating agent tokens and pipelines)
     - `read_pipelines`
     - `write_pipelines`
     - `read_organizations`
   - Set in `terraform.tfvars` as `buildkite_api_token`

2. **AWS Credentials**
   - AWS CLI configured with appropriate permissions
   - Permissions needed: EC2, S3, IAM, SSM, CloudFormation

## Setup Instructions

### 1. Configure Buildkite API Token

The Buildkite API token is used by Terraform to create agent tokens and pipelines automatically.

**Create a new API token:**
1. Go to https://buildkite.com/user/api-access-tokens/new
2. Select these scopes:
   - ☑ `graphql` (required)
   - ☑ `read_pipelines`
   - ☑ `write_pipelines`
   - ☑ `read_organizations`
3. Click "Create New API Access Token"
4. Copy the token

**Configure in terraform.tfvars:**
```hcl
buildkite_api_token = "bkua_xxxxxxxxxxxxxxxxxxxxx"
```

Or use environment variable:
```bash
export TF_VAR_buildkite_api_token="bkua_xxxxxxxxxxxxxxxxxxxxx"
```

**Note:** Terraform will automatically create the agent token for you. You don't need to manually create an agent token.

### 2. (Optional) Upload Environment Files to S3

If your benchmarks need specific environment variables (API tokens, credentials, etc.), create environment files and upload them to S3:

```bash
# Create environment file for a specific queue
cat > env <<EOF
export ARROW_BCI_URL=https://your-arrow-bci-url
export CONBENCH_TOKEN=your-conbench-api-token
export CONBENCH_URL=https://conbench.arrow-dev.org
export CONBENCH_CLI=conbench-v2
export GITHUB_PAT=your-github-token
EOF

# Upload to S3 (will be created by Terraform)
aws s3 cp env "s3://conbench-prod-buildkite-secrets/queues/arm64-t4g-2xlarge-linux/env" \
  --sse AES256 --profile arrow-admin
```

The bootstrap script will automatically download and source this file for agents in that queue.

### 3. Deploy Infrastructure

```bash
cd terraform

# Initialize Terraform (first time only)
terraform init

# Review the plan
terraform plan -var-file=terraform.tfvars

# Apply the configuration
terraform apply -var-file=terraform.tfvars
```

**What happens during deployment:**
1. Terraform creates an agent token in Buildkite via the API
2. The token is stored in AWS SSM Parameter Store
3. Three CloudFormation stacks are created for the agent types
4. A test pipeline is created in Buildkite

### 4. Verify Deployment

After deployment, check:

```bash
# View outputs
terraform output

# Check CloudFormation stacks
aws cloudformation list-stacks \
  --stack-status-filter CREATE_COMPLETE UPDATE_COMPLETE \
  --query "StackSummaries[?contains(StackName, 'buildkite')].StackName" \
  --profile arrow-admin

# Check S3 bucket
aws s3 ls s3://conbench-prod-buildkite-secrets/ --profile arrow-admin
```

## Using the Agents

### Queue Names

Your Buildkite pipelines should target these queues:

```yaml
# .buildkite/pipeline.yml
steps:
  - label: "ARM64 Benchmark"
    command: "make benchmark"
    agents:
      queue: "arm64-t4g-2xlarge-linux"

  - label: "AMD64 General Purpose Benchmark"
    command: "make benchmark"
    agents:
      queue: "amd64-m5-4xlarge-linux"

  - label: "AMD64 Compute Optimized Benchmark"
    command: "make benchmark"
    agents:
      queue: "amd64-c6a-4xlarge-linux"
```

### Agent Tags

Agents are also tagged for more granular selection:

- **ARM64 agents**: `arch=arm64`, `os=linux`, `instance=t4g-2xlarge`
- **AMD64 M5 agents**: `arch=amd64`, `os=linux`, `instance=m5-4xlarge`
- **AMD64 C6a agents**: `arch=amd64`, `os=linux`, `instance=c6a-4xlarge`

Example using tags:

```yaml
steps:
  - label: "Benchmark on ARM64"
    command: "make benchmark"
    agents:
      arch: "arm64"
      os: "linux"
```

## Bootstrap Script

The bootstrap script (`buildkite-bootstrap.sh`) automatically sets up each agent with:

- **Build Tools**: cmake, gcc, g++, make, ninja-build
- **Python**: Python 3 with pip
- **Conda**: Miniconda3 for managing Python environments
- **Docker**: Docker CE for containerized builds
- **Arrow Dependencies**: Required libraries for building Apache Arrow
- **Git Configuration**: Basic git setup
- **System Tuning**: Increased file limits and network performance tuning

## Monitoring and Scaling

### Auto-Scaling

- Agents automatically scale from **0 to 4 instances** based on queue depth
- Idle agents shut down after 15 minutes (default Buildkite behavior)
- Scaling is managed by the Buildkite AWS Stack's Lambda function

### Monitoring

```bash
# Check agent status in Buildkite UI
# https://buildkite.com/organizations/YOUR_ORG/agents

# View CloudFormation stack events
aws cloudformation describe-stack-events \
  --stack-name conbench-prod-buildkite-arm64-t4g-2xlarge-linux \
  --profile arrow-admin

# Check EC2 instances
aws ec2 describe-instances \
  --filters "Name=tag:Queue,Values=arm64-t4g-2xlarge-linux" \
  --profile arrow-admin
```

## Updating

### Update AMIs

AMIs should be updated periodically for security patches:

1. Find latest Amazon Linux 2023 AMIs:
   ```bash
   # AMD64
   aws ec2 describe-images \
     --owners amazon \
     --filters "Name=name,Values=al2023-ami-2023*-x86_64" \
     --query 'sort_by(Images, &CreationDate)[-1].[ImageId,Name]' \
     --output table \
     --profile arrow-admin

   # ARM64
   aws ec2 describe-images \
     --owners amazon \
     --filters "Name=name,Values=al2023-ami-2023*-arm64" \
     --query 'sort_by(Images, &CreationDate)[-1].[ImageId,Name]' \
     --output table \
     --profile arrow-admin
   ```

2. Update `terraform.tfvars`:
   ```hcl
   buildkite_agent_amis = {
     "amd64-linux" = "ami-NEW-AMD64-ID"
     "arm64-linux" = "ami-NEW-ARM64-ID"
   }
   ```

3. Apply changes:
   ```bash
   terraform apply -var-file=terraform.tfvars
   ```

### Update Bootstrap Script

1. Edit `terraform/buildkite-bootstrap.sh`
2. Apply to update S3 object:
   ```bash
   terraform apply -var-file=terraform.tfvars
   ```
3. New agents will use the updated script (existing agents won't be affected)

## Troubleshooting

### Agents Not Starting

1. Check CloudFormation stack events for errors
2. Verify Buildkite agent token is correct in SSM Parameter Store
3. Check bootstrap script logs on the EC2 instance:
   ```bash
   ssh -i your-key.pem ec2-user@INSTANCE_IP
   sudo cat /var/log/buildkite-agent.log
   ```

### Permission Issues

1. Verify IAM policies are attached to instance role
2. Check S3 bucket permissions for secrets bucket
3. Ensure SSM Parameter Store allows GetParameter

### Bootstrap Script Failures

1. SSH to instance and check cloud-init logs:
   ```bash
   sudo cat /var/log/cloud-init-output.log
   ```

2. Check bootstrap script execution:
   ```bash
   sudo cat /var/lib/cloud/instance/user-data.txt
   ```

## Cost Optimization

- Agents shut down when idle (saves money)
- Adjust `min_size` and `max_size` in `terraform/buildkite.tf` to control costs
- Consider using Spot instances for cost savings (requires template modification)

## Architecture

```
Buildkite Job
    ↓
Buildkite Queue (e.g., arm64-t4g-2xlarge-linux)
    ↓
CloudFormation Stack
    ↓
Auto Scaling Group
    ↓
EC2 Instances (0-4)
    ↓
Bootstrap Script (setup)
    ↓
Buildkite Agent (running)
```

## Resources Created

- 3 CloudFormation stacks (one per agent type)
- 3 Auto Scaling Groups
- 1 S3 bucket for secrets and bootstrap scripts
- 1 SSM Parameter for Buildkite agent token
- 1 IAM policy for agent permissions
- 3 IAM roles (created by CloudFormation)

## Next Steps

After setup, you can:

1. Add Buildkite pipelines to your repositories
2. Configure webhooks for automatic builds
3. Set up notification integrations (Slack, email, etc.)
4. Monitor costs and adjust scaling parameters

For more information, see:
- [Buildkite AWS Stack Documentation](https://github.com/buildkite/elastic-ci-stack-for-aws)
- [Arrow Benchmarks CI](https://github.com/arctosalliance/arrow-benchmarks-ci)
