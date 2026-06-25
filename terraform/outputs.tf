# VPC Outputs
output "vpc_id" {
  description = "VPC ID"
  value       = aws_vpc.main.id
}

output "private_subnet_ids" {
  description = "Private subnet IDs"
  value       = aws_subnet.private[*].id
}

output "public_subnet_ids" {
  description = "Public subnet IDs"
  value       = aws_subnet.public[*].id
}

# EKS Outputs
output "eks_cluster_id" {
  description = "EKS cluster ID"
  value       = aws_eks_cluster.conbench.id
}

output "eks_cluster_name" {
  description = "EKS cluster name"
  value       = aws_eks_cluster.conbench.name
}

output "eks_cluster_endpoint" {
  description = "EKS cluster endpoint"
  value       = aws_eks_cluster.conbench.endpoint
}

output "eks_cluster_security_group_id" {
  description = "Security group ID attached to the EKS cluster"
  value       = aws_eks_cluster.conbench.vpc_config[0].cluster_security_group_id
}

output "eks_cluster_certificate_authority" {
  description = "EKS cluster certificate authority data"
  value       = aws_eks_cluster.conbench.certificate_authority[0].data
  sensitive   = true
}

output "eks_cluster_oidc_issuer_url" {
  description = "OIDC issuer URL for the EKS cluster"
  value       = aws_eks_cluster.conbench.identity[0].oidc[0].issuer
}

output "eks_node_group_id" {
  description = "EKS node group ID"
  value       = aws_eks_node_group.conbench.id
}

output "eks_node_group_status" {
  description = "Status of the EKS node group"
  value       = aws_eks_node_group.conbench.status
}

# RDS Outputs
output "rds_instance_id" {
  description = "RDS instance ID"
  value       = aws_db_instance.conbench.id
}

output "rds_instance_endpoint" {
  description = "RDS instance connection endpoint"
  value       = aws_db_instance.conbench.endpoint
}

output "rds_instance_address" {
  description = "RDS instance address (hostname)"
  value       = aws_db_instance.conbench.address
}

output "rds_instance_port" {
  description = "RDS instance port"
  value       = aws_db_instance.conbench.port
}

output "rds_database_name" {
  description = "Name of the database"
  value       = aws_db_instance.conbench.db_name
}

output "rds_master_username" {
  description = "Master username for RDS"
  value       = aws_db_instance.conbench.username
  sensitive   = true
}

# Arrow BCI RDS Outputs
output "arrow_bci_rds_endpoint" {
  description = "Arrow BCI RDS instance endpoint"
  value       = aws_db_instance.arrow_bci.endpoint
}

output "arrow_bci_rds_address" {
  description = "Arrow BCI RDS instance address (hostname)"
  value       = aws_db_instance.arrow_bci.address
}

output "arrow_bci_rds_instance_port" {
  description = "Arrow BCI RDS instance port"
  value       = aws_db_instance.arrow_bci.port
}

output "arrow_bci_rds_database_name" {
  description = "Name of the Arrow BCI database"
  value       = aws_db_instance.arrow_bci.db_name
}

output "arrow_bci_rds_master_username" {
  description = "Master username for Arrow BCI RDS"
  value       = aws_db_instance.arrow_bci.username
  sensitive   = true
}

output "arrow_bci_db_connection_string" {
  description = "Arrow BCI database connection information (use with caution in logs)"
  value       = "postgresql://${aws_db_instance.arrow_bci.username}@${aws_db_instance.arrow_bci.address}:${aws_db_instance.arrow_bci.port}/${aws_db_instance.arrow_bci.db_name}"
  sensitive   = true
}

# Security Group Outputs
output "eks_nodes_security_group_id" {
  description = "Security group ID for EKS worker nodes"
  value       = aws_security_group.eks_nodes.id
}

output "rds_security_group_id" {
  description = "Security group ID for RDS instance"
  value       = aws_security_group.rds.id
}

# Configuration Outputs
output "configure_kubectl" {
  description = "Command to configure kubectl"
  value       = "aws eks update-kubeconfig --region ${var.aws_region} --name ${aws_eks_cluster.conbench.name}"
}

output "db_connection_string" {
  description = "Database connection information (use with caution in logs)"
  value       = "postgresql://${aws_db_instance.conbench.username}@${aws_db_instance.conbench.address}:${aws_db_instance.conbench.port}/${aws_db_instance.conbench.db_name}"
  sensitive   = true
}

# Route53 and Domain Outputs - arrow-dev.org
output "arrow_dev_zone_id" {
  description = "arrow-dev.org hosted zone ID"
  value       = data.aws_route53_zone.arrow_dev.zone_id
}

output "arrow_dev_certificate_arn" {
  description = "ACM certificate ARN for arrow-dev.org - use this in your Kubernetes ingress"
  value       = aws_acm_certificate.arrow_dev.arn
}

output "arrow_dev_certificate_status" {
  description = "ACM certificate validation status for arrow-dev.org"
  value       = aws_acm_certificate.arrow_dev.status
}

output "conbench_url" {
  description = "Conbench application URL"
  value       = "https://conbench.arrow-dev.org"
}

output "conbench_v2_url" {
  description = "Conbench v2 evaluator URL"
  value       = var.conbench_v2_enabled ? var.conbench_v2_public_url : "Not created"
}

output "conbench_v2_deployment_name" {
  description = "Conbench v2 evaluator Deployment name"
  value       = try(kubernetes_deployment.conbench_v2[0].metadata[0].name, "Not created")
}

output "conbench_v2_service_name" {
  description = "Conbench v2 evaluator Service name"
  value       = try(kubernetes_service.conbench_v2[0].metadata[0].name, "Not created")
}

output "conbench_v2_service_hostname" {
  description = "Conbench v2 evaluator LoadBalancer hostname"
  value       = var.conbench_v2_enabled && var.conbench_v2_expose_load_balancer ? "Check with: kubectl -n ${var.conbench_v2_namespace} get svc conbench-v2-service -o jsonpath='{.status.loadBalancer.ingress[0].hostname}'" : "Not exposed"
}

output "conbench_v2_port_forward_command" {
  description = "Private smoke command for the Conbench v2 evaluator"
  value       = var.conbench_v2_enabled ? "kubectl -n ${var.conbench_v2_namespace} port-forward service/conbench-v2-service 18080:80" : "Not created"
}

# Route53 and Domain Outputs - Custom Domain (if configured)
output "route53_zone_id" {
  description = "Route53 hosted zone ID for custom domain"
  value       = try(aws_route53_zone.main[0].zone_id, "")
}

output "route53_nameservers" {
  description = "Route53 nameservers - configure these in Cloudflare"
  value       = try(aws_route53_zone.main[0].name_servers, [])
}

output "acm_certificate_arn" {
  description = "ACM certificate ARN for custom domain - use this in your Kubernetes ingress"
  value       = try(aws_acm_certificate.main[0].arn, "")
}

output "acm_certificate_status" {
  description = "ACM certificate validation status for custom domain"
  value       = try(aws_acm_certificate.main[0].status, "")
}

output "domain_name" {
  description = "Configured domain name"
  value       = var.domain_name
}

# CloudFront and Crossbow Outputs
output "crossbow_subdomain_url" {
  description = "Crossbow subdomain URL"
  value       = var.create_crossbow_subdomain ? "https://crossbow.arrow-dev.org" : "Not created"
}

output "cloudfront_distribution_id" {
  description = "CloudFront distribution ID for crossbow subdomain"
  value       = var.create_crossbow_subdomain ? aws_cloudfront_distribution.crossbow[0].id : "Not created"
}

output "cloudfront_domain_name" {
  description = "CloudFront domain name"
  value       = var.create_crossbow_subdomain ? aws_cloudfront_distribution.crossbow[0].domain_name : "Not created"
}

# Deployment Configuration Hints
output "deployment_hints" {
  description = "Hints for deploying Conbench application"
  value = {
    conbench_url              = "https://conbench.arrow-dev.org"
    benchmarks_data_public    = "true"
    db_name                   = "conbench_prod"
    deployment_script         = "./terraform/deploy-conbench-to-eks.sh"
    required_env_vars         = ["DB_PASSWORD", "SECRET_KEY", "REGISTRATION_KEY"]
  }
}

# # Buildkite Outputs
# output "buildkite_agent_queues" {
#   description = "Buildkite agent queue names"
#   value       = [for k, v in local.buildkite_stacks : v.queue]
# }
#
# output "buildkite_stack_names" {
#   description = "CloudFormation stack names for Buildkite agents"
#   value       = { for k, v in aws_cloudformation_stack.buildkite_agents : k => v.name }
# }

# Arrow BCI Kubernetes Outputs
output "arrow_bci_url" {
  description = "Arrow BCI application URL"
  value       = "https://arrow-bci.arrow-dev.org"
}

output "arrow_bci_health_check_url" {
  description = "Arrow BCI health check endpoint"
  value       = "https://arrow-bci.arrow-dev.org/health-check"
}

output "arrow_bci_service_hostname" {
  description = "Arrow BCI LoadBalancer hostname (run 'kubectl get svc arrow-bci-service' to see actual value)"
  value       = "Check with: kubectl get svc arrow-bci-service -o jsonpath='{.status.loadBalancer.ingress[0].hostname}'"
}

# ECR Outputs
output "ecr_repository_conbench_url" {
  description = "ECR repository URL for Conbench"
  value       = aws_ecr_repository.conbench.repository_url
}

output "ecr_repository_arrow_bci_url" {
  description = "ECR repository URL for Arrow BCI"
  value       = aws_ecr_repository.arrow_bci.repository_url
}

output "ecr_repository_conbench_arn" {
  description = "ECR repository ARN for Conbench"
  value       = aws_ecr_repository.conbench.arn
}

output "ecr_repository_arrow_bci_arn" {
  description = "ECR repository ARN for Arrow BCI"
  value       = aws_ecr_repository.arrow_bci.arn
}

output "arrow_bci_deployment_name" {
  description = "Arrow BCI deployment name"
  value       = kubernetes_deployment.arrow_bci.metadata[0].name
}
