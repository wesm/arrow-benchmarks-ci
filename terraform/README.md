# Conbench AWS EKS Terraform Configuration

This Terraform configuration deploys a complete Conbench infrastructure on AWS, including:

- **VPC** with public and private subnets across 2 availability zones
- **EKS Cluster** with managed node group
- **RDS PostgreSQL** instance (can restore from snapshot)
- **Security Groups** and IAM roles
- **NAT Gateway** for private subnet internet access

## Prerequisites

1. **AWS CLI** configured with appropriate credentials
2. **Terraform** >= 1.0 installed
3. **kubectl** for EKS cluster management
4. AWS account with permissions to create EKS, RDS, VPC, and IAM resources

## Quick Start

### 1. Configure Variables

Copy the example variables file and customize it:

```bash
cd terraform
cp terraform.tfvars.example terraform.tfvars
```

Edit `terraform.tfvars` with your values:

- Set `db_snapshot_identifier` to your RDS snapshot ARN if restoring from backup
- Update `allowed_cidr_blocks` to restrict EKS API access
- Set strong `db_password` if creating a new database
- Adjust instance types and sizes based on your needs

### 2. Initialize Terraform

```bash
terraform init
```

### 3. Review the Plan

```bash
terraform plan
```

### 4. Deploy Infrastructure

```bash
terraform apply
```

This will take approximately 15-20 minutes as EKS cluster creation is slow.

### 5. Configure kubectl

After deployment, configure kubectl to access your cluster:

```bash
aws eks update-kubeconfig --region us-east-1 --name conbench-prod --profile arrow-admin
```

Or use the output command:

```bash
terraform output -raw configure_kubectl | bash
```

## Restoring from RDS Snapshot

If you have an existing RDS snapshot, set the snapshot identifier in `terraform.tfvars`:

```hcl
db_snapshot_identifier = "arn:aws:rds:us-east-1:123456789012:snapshot:conbench-snapshot-2024-01-15"
```

**Important Notes:**
- When restoring from a snapshot, `db_name`, `db_username`, and `db_password` are ignored
- The database will be created with the credentials from the snapshot
- You may need to reset the master password after restoration if credentials are lost
- The snapshot must be in the same AWS region as your deployment

## Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                          VPC (10.0.0.0/16)                  │
│                                                             │
│  ┌──────────────────┐              ┌──────────────────┐    │
│  │  Public Subnet 1 │              │  Public Subnet 2 │    │
│  │  (ALB, NAT GW)   │              │                  │    │
│  └──────────────────┘              └──────────────────┘    │
│          │                                  │               │
│          │           Internet Gateway       │               │
│          └──────────────────┬───────────────┘               │
│                            │                                │
│  ┌──────────────────┐              ┌──────────────────┐    │
│  │ Private Subnet 1 │              │ Private Subnet 2 │    │
│  │ (EKS Nodes, RDS) │              │ (EKS Nodes, RDS) │    │
│  └──────────────────┘              └──────────────────┘    │
│          │                                  │               │
│     ┌────▼──────────────────────────────────▼────┐          │
│     │          EKS Worker Nodes                  │          │
│     │       (Conbench Application Pods)          │          │
│     └────────────────────────────────────────────┘          │
│                                                             │
│     ┌────────────────────────────────────────────┐          │
│     │      RDS PostgreSQL (Multi-AZ optional)    │          │
│     └────────────────────────────────────────────┘          │
└─────────────────────────────────────────────────────────────┘
```

## Configuration Details

### EKS Cluster

- **Kubernetes Version**: 1.28 (configurable)
- **Node Group**: 2 nodes by default (min: 1, max: 4)
- **Instance Type**: t3.medium (configurable)
- **Networking**: Private subnets with NAT gateway for outbound traffic

### RDS PostgreSQL

- **Engine**: PostgreSQL 15.5
- **Instance Class**: db.t3.medium (configurable)
- **Storage**: 100 GB with autoscaling up to 500 GB
- **Backups**: 7-day retention period
- **Monitoring**: Enhanced monitoring and Performance Insights enabled
- **Encryption**: Storage encryption enabled

### Security

- EKS cluster endpoint accessible from configured CIDR blocks
- Worker nodes in private subnets
- RDS accessible only from EKS worker nodes
- All traffic encrypted in transit and at rest

## Outputs

After deployment, Terraform provides these outputs:

```bash
# View all outputs
terraform output

# Get specific values
terraform output eks_cluster_name
terraform output rds_instance_endpoint
```

Key outputs:
- `eks_cluster_name`: Name of the EKS cluster
- `eks_cluster_endpoint`: EKS API endpoint
- `rds_instance_address`: RDS hostname
- `rds_instance_port`: RDS port (5432)
- `configure_kubectl`: Command to configure kubectl

## Deploying Conbench Application

After infrastructure is created:

1. **Update Kubernetes manifests** with RDS endpoint:
   ```bash
   export DB_HOST=$(terraform output -raw rds_instance_address)
   export DB_PORT=$(terraform output -raw rds_instance_port)
   ```

2. **Create Kubernetes secrets** for database credentials

3. **Apply Kubernetes manifests** from `../k8s/` directory

4. **Deploy ALB Ingress Controller** (required for LoadBalancer services):
   ```bash
   # See https://kubernetes-sigs.github.io/aws-load-balancer-controller/
   ```

## Conbench v2 Evaluator

Use [CONBENCH_V2_EVALUATOR.md](CONBENCH_V2_EVALUATOR.md) for the
Terraform-managed parallel Conbench v2 evaluator. The evaluator must be created
through reviewed infrastructure code, not through manual Kubernetes manifests
or console DNS changes.

## Cost Estimation

Approximate monthly costs (us-east-1, on-demand pricing):

- EKS Control Plane: $73/month
- EC2 Instances (2x t3.medium): ~$60/month
- RDS (db.t3.medium): ~$70/month
- NAT Gateway: ~$32/month + data transfer
- **Total: ~$235/month** (excluding data transfer and storage costs)

## Maintenance

### Updating Kubernetes Version

```bash
# Update variable in terraform.tfvars
kubernetes_version = "1.29"

# Apply changes
terraform apply
```

### Scaling Nodes

```bash
# Update variables in terraform.tfvars
node_group_desired_size = 4

# Apply changes
terraform apply
```

### Database Backup

Automated backups are configured with 7-day retention. Manual snapshots:

```bash
aws rds create-db-snapshot \
  --db-instance-identifier $(terraform output -raw rds_instance_id) \
  --db-snapshot-identifier conbench-manual-$(date +%Y%m%d-%H%M%S)
```

## Cleanup

To destroy all resources:

```bash
terraform destroy
```

**Warning**: This will delete all resources including the database. Ensure you have backups!

## Security Considerations

1. **Restrict API Access**: Update `allowed_cidr_blocks` to specific IPs/ranges
2. **Enable Multi-AZ**: Set `db_multi_az = true` for production
3. **Strong Passwords**: Use AWS Secrets Manager for database credentials
4. **Enable AWS GuardDuty**: For threat detection
5. **Configure CloudTrail**: For audit logging
6. **Use Private Endpoints**: Consider VPC endpoints for AWS services

## Troubleshooting

### EKS Nodes Not Joining Cluster

Check node IAM role permissions and security groups:
```bash
kubectl get nodes
aws eks describe-nodegroup --cluster-name $(terraform output -raw eks_cluster_name) --nodegroup-name conbench-prod-node-group --profile arrow-admin --region us-east-1
```

### Cannot Access RDS

Verify security group rules and network connectivity:
```bash
# From within a pod
kubectl run -it --rm debug --image=postgres:15 --restart=Never -- psql -h DB_HOST -U DB_USER -d DB_NAME
kubectl run -it --rm debug --image=postgres:15 --restart=Never -- psql -h $DB_HOST -U $DB_USER -d conbench-prod-db
```

### Terraform State Issues

If state becomes corrupted:
```bash
terraform refresh
terraform state list
```

## References

- [Conbench Documentation](https://conbench.github.io/conbench)
- [AWS EKS Best Practices](https://aws.github.io/aws-eks-best-practices/)
- [Terraform AWS Provider](https://registry.terraform.io/providers/hashicorp/aws/latest/docs)
