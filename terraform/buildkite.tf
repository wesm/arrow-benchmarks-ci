# Buildkite Agent Infrastructure for Arrow Benchmarks

resource "buildkite_agent_token" "token_for_agents_in_arrow_computing_aws" {
  description = "BK agent token for Benchmark Machines on Arrow AWS account (NEW)"
}


# # Arrow Benchmarks CI Pipelines
# resource "buildkite_pipeline" "arrow_bci_pipelines" {
#   for_each       = local.arrow_bci_pipelines
#   name           = each.key
#   repository     = "https://github.com/arctosalliance/arrow-benchmarks-ci.git"
#   default_branch = "main"
#
#   steps = <<-EOT
#   env:
#     BUILDKITE_API_BASE_URL: "${var.buildkite_api_base_url}"
#     BUILDKITE_ORG: "${var.buildkite_org}"
#     CONBENCH_URL: "${var.conbench_url}"
#     DB_PORT: "${var.db_port}"
#     ENV: "${var.environment}"
#     FLASK_APP: "${var.flask_app}"
#     GITHUB_API_BASE_URL: "${var.github_api_base_url}"
#     GITHUB_REPO: "${var.github_repo}"
#     GITHUB_REPO_WITH_BENCHMARKABLE_COMMITS: "${var.github_repo_with_benchmarkable_commits}"
#     MAX_COMMITS_TO_FETCH: "${var.max_commits_to_fetch}"
#     PIPY_API_BASE_URL: "${var.pypi_api_base_url}"
#     PIPY_PROJECT: "${var.pypi_project}"
#     SLACK_API_BASE_URL: "${var.slack_api_base_url}"
#   agents:
#     queue: "${each.value.queue}"
#   steps:
#     - label: ":pipeline: Pipeline upload"
#       command: buildkite-agent pipeline upload buildkite/${each.value.folder}/pipeline.yml
#   EOT
#
#   provider_settings = {
#     trigger_mode                                  = each.value.trigger_mode
#     publish_commit_status                         = each.value.publish_commit_status
#     build_branches                                = each.value.build_branches
#     build_pull_requests                           = each.value.build_pull_requests
#     skip_pull_request_builds_for_existing_commits = each.value.skip_pull_request_builds_for_existing_commits
#   }
#
#   cancel_intermediate_builds = each.value.cancel_intermediate_builds
# }

locals {
  new-conbench_pipelines = {
    new-conbench-deploy = {
      folder                                        = "conbench-deploy"
      trigger_mode                                  = "none"
      publish_commit_status                         = false
      build_branches                                = false
      build_pull_requests                           = false
      skip_pull_request_builds_for_existing_commits = true
    }
    new-conbench-rollback = {
      folder                                        = "conbench-rollback"
      trigger_mode                                  = "none"
      publish_commit_status                         = false
      build_branches                                = false
      build_pull_requests                           = false
      skip_pull_request_builds_for_existing_commits = true
    }
    # new-conbench-deploy-velox = {
    #   folder                                        = "conbench-deploy"
    #   trigger_mode                                  = "none"
    #   publish_commit_status                         = false
    #   build_branches                                = false
    #   build_pull_requests                           = false
    #   skip_pull_request_builds_for_existing_commits = true
    # }
    # new-conbench-rollback-velox = {
    #   folder                                        = "conbench-rollback"
    #   trigger_mode                                  = "none"
    #   publish_commit_status                         = false
    #   build_branches                                = false
    #   build_pull_requests                           = false
    #   skip_pull_request_builds_for_existing_commits = true
    # }
  }
  webhooks_pipelines = {
    new-webhooks-deploy = {
      folder                                        = "deploy"
      trigger_mode                                  = "none"
      publish_commit_status                         = false
      build_branches                                = false
      build_pull_requests                           = false
      skip_pull_request_builds_for_existing_commits = true
    }
    new-webhooks-rollback = {
      folder                                        = "rollback"
      trigger_mode                                  = "none"
      publish_commit_status                         = false
      build_branches                                = false
      build_pull_requests                           = false
      skip_pull_request_builds_for_existing_commits = true
    }
    new-webhooks-test = {
      folder                                        = "test"
      trigger_mode                                  = "code"
      publish_commit_status                         = true
      build_branches                                = true
      build_pull_requests                           = true
      skip_pull_request_builds_for_existing_commits = true
    }
  }
  new-arrow_bci_pipelines = {
    new-arrow-bci-deploy = {
      folder                                        = "deploy"
      queue                                         = aws_cloudformation_stack.arrow-bci.parameters.BuildkiteQueue
      trigger_mode                                  = "code"
      publish_commit_status                         = true
      build_branches                                = true
      build_pull_requests                           = false
      skip_pull_request_builds_for_existing_commits = true
      cancel_intermediate_builds                    = false
    }
    new-arrow-bci-schedule-and-publish = {
      folder                                        = "schedule_and_publish"
      queue                                         = aws_cloudformation_stack.arrow-bci.parameters.BuildkiteQueue
      trigger_mode                                  = "none"
      publish_commit_status                         = false
      build_branches                                = false
      build_pull_requests                           = false
      skip_pull_request_builds_for_existing_commits = true
      cancel_intermediate_builds                    = true
    }
    new-arrow-bci-test = {
      folder                                        = "test"
      queue                                         = aws_cloudformation_stack.arrow-bci-test.parameters.BuildkiteQueue
      trigger_mode                                  = "code"
      publish_commit_status                         = true
      build_branches                                = true
      build_pull_requests                           = true
      skip_pull_request_builds_for_existing_commits = true
      cancel_intermediate_builds                    = false
    }
    new-arrow-bci-benchmark-build-test = {
      folder                                        = "benchmark-test"
      queue                                         = aws_cloudformation_stack.arrow-bci-benchmark-build-test.parameters.BuildkiteQueue
      trigger_mode                                  = "none"
      publish_commit_status                         = false
      build_branches                                = false
      build_pull_requests                           = false
      skip_pull_request_builds_for_existing_commits = true
      cancel_intermediate_builds                    = false
    }
  }
}

resource "buildkite_pipeline" "conbench_pipelines" {
  for_each       = local.new-conbench_pipelines
  name           = each.key
  repository     = "https://github.com/arctosalliance/conbench.git"
  steps          = <<-EOT
  env:
    DOCKER_REGISTRY: "${aws_ssm_parameter.docker_registry.value}"
    FLASK_APP:       "conbench"
    PIPY_API_BASE_URL:    "${var.pypi_api_base_url}"
    PIPY_PROJECT:         "${var.pypi_project}"
    EKS_CLUSTER:          "${var.eks_cluster_name}"
    NAMESPACE:            "default"
    DISTRIBUTION_COMMITS: "100"
    APPLICATION_NAME: "Conbench"
    BENCHMARKS_DATA_PUBLIC: "true"
    CONBENCH_INTENDED_BASE_URL: "${var.conbench_url}"
    CONBENCH_URL: "${var.conbench_url}"
    CONBENCH_API_TOKEN:   "${var.conbench_api_token}"
    GITHUB_API_TOKEN:     "${var.github_api_token}"
    DB_NAME:              "${var.db_name_conbench}"
    DB_PORT:              "${var.db_port}"
    DB_USERNAME:          "${var.db_username}"
    DB_HOST:              "${aws_db_instance.conbench.address}"
    DB_PASSWORD:          "${var.db_password}"
    # SVS_TYPE: ""  # or appropriate value
  agents:
    queue: "${aws_cloudformation_stack.conbench.parameters.BuildkiteQueue}"
  steps:
    - label: ":pipeline: Pipeline upload"
      command: buildkite-agent pipeline upload .buildkite/${each.value.folder}/pipeline.yml
  EOT
  default_branch = "main"
  provider_settings = {
    trigger_mode                                  = each.value.trigger_mode
    publish_commit_status                         = each.value.publish_commit_status
    build_branches                                = each.value.build_branches
    build_pull_requests                           = each.value.build_pull_requests
    skip_pull_request_builds_for_existing_commits = each.value.skip_pull_request_builds_for_existing_commits
  }
}

# resource "buildkite_pipeline" "webhooks_pipelines" {
#   for_each       = local.webhooks_pipelines
#   name           = each.key
#   repository     = "git@github.com:arctosalliance/webhooks.git"
#   steps          = <<-EOT
#   agents:
#     queue: "${aws_cloudformation_stack.conbench.parameters.BuildkiteQueue}"
#   steps:
#     - label: ":pipeline: Pipeline upload"
#       command: buildkite-agent pipeline upload .buildkite/${each.value.folder}/pipeline.yml
#   EOT
#   default_branch = "main"
#   provider_settings = {
#     trigger_mode                                  = each.value.trigger_mode
#     publish_commit_status                         = each.value.publish_commit_status
#     build_branches                                = each.value.build_branches
#     build_pull_requests                           = each.value.build_pull_requests
#     skip_pull_request_builds_for_existing_commits = each.value.skip_pull_request_builds_for_existing_commits
#   }
# }

resource "buildkite_pipeline" "arrow_bci_pipelines" {
  for_each       = local.new-arrow_bci_pipelines
  name           = each.key
  repository     = "https://github.com/arctosalliance/arrow-benchmarks-ci.git"
  steps          = <<-EOT
  env:
    DOCKER_REGISTRY:      "${aws_ssm_parameter.docker_registry.value}"
    FLASK_APP:            "arrow-bci"
    DB_PORT:              "${var.db_port}"
    GITHUB_API_BASE_URL:  "${var.github_api_base_url}"
    MAX_COMMITS_TO_FETCH: "${var.max_commits_to_fetch}"
    CONBENCH_URL:         "${var.conbench_url}"
    DB_USERNAME:          "${var.db_username}"
    DB_HOST:              "${var.db_host}"
    DB_PASSWORD:          "${var.db_password_arrow_bci}"
    DB_NAME:              "${var.db_name_arrow_bci}"
    GITHUB_API_TOKEN:     "${var.github_api_token}"
    GITHUB_APP_ID:        "${var.github_app_id}"
    GITHUB_APP_INSTALLATION_ID: "${var.github_app_installation_id}"
    PIPY_API_BASE_URL:    "${var.pypi_api_base_url}"
    PIPY_PROJECT:         "${var.pypi_project}"
    BUILDKITE_API_BASE_URL: "${var.buildkite_api_base_url}"
    BUILDKITE_ORG:        "${var.buildkite_org}"
    ENV:                  "${var.environment}"
    GITHUB_REPO:          "${var.github_repo}"
    GITHUB_REPO_WITH_BENCHMARKABLE_COMMITS: "${var.github_repo_with_benchmarkable_commits}"
    BUILDKITE_API_TOKEN:  "${var.buildkite_api_token}"
    EKS_CLUSTER:          "${var.eks_cluster_name}"
    SLACK_API_BASE_URL:   "${var.slack_api_base_url}"
    NAMESPACE:            "default"
  agents:
    queue: "${each.value.queue}"
  steps:
    - label: ":pipeline: Pipeline upload"
      command: buildkite-agent pipeline upload buildkite/${each.value.folder}/pipeline.yml
  EOT
  default_branch = "main"
  provider_settings = {
    trigger_mode                                  = each.value.trigger_mode
    publish_commit_status                         = each.value.publish_commit_status
    build_branches                                = each.value.build_branches
    build_pull_requests                           = each.value.build_pull_requests
    skip_pull_request_builds_for_existing_commits = each.value.skip_pull_request_builds_for_existing_commits
  }
  cancel_intermediate_builds = each.value.cancel_intermediate_builds
}

resource "buildkite_pipeline_schedule" "every_15_mins" {
  pipeline_id = buildkite_pipeline.arrow_bci_pipelines["new-arrow-bci-schedule-and-publish"].id
  label       = "Every 15 minutes"
  cronline    = "*/15 * * * *"
  branch      = buildkite_pipeline.arrow_bci_pipelines["new-arrow-bci-schedule-and-publish"].default_branch
  enabled     = true
}
