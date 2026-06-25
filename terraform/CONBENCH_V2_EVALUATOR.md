# Conbench v2 Evaluator

This page describes the Terraform-managed Conbench v2 evaluator for Arrow
maintainer review. The evaluator must not be created with one-off `kubectl`
manifests, console DNS edits, or host-local processes.

The first evaluator is read-only and parallel to the legacy Python Conbench
deployment:

```text
legacy Conbench     -> conbench-service    -> conbench.arrow-dev.org
Conbench v2 review  -> conbench-v2-service -> conbench-v2.arrow-dev.org
```

## Resources

`conbench_v2_evaluator.tf` manages:

- `kubernetes_config_map.conbench_v2`
- `kubernetes_secret.conbench_v2`
- `kubernetes_deployment.conbench_v2`
- `kubernetes_service.conbench_v2`
- optional `aws_route53_record.conbench_v2`

All resource names and labels use `conbench-v2`, so the evaluator does not
share selectors with the legacy `conbench-service`.

## Safe First Plan

Create a local `conbench-v2-evaluator.tfvars` from
`conbench-v2-evaluator.tfvars.example`. Do not copy the broad
`terraform.tfvars.example` into a production plan just to add the evaluator;
that file is a baseline example for the whole stack, while this rollout should
be scoped to `conbench-v2-*` resources.

Keep `conbench_v2_expose_load_balancer = false` and
`conbench_v2_create_dns_record = false` for the first plan so the Service is
created as `ClusterIP` and can be smoke-tested privately before any public ELB
or DNS exists.

Required values:

```hcl
aws_profile = "arrow-conbench"

conbench_v2_enabled = true
conbench_v2_image   = "855673865593.dkr.ecr.us-east-1.amazonaws.com/conbench:<immutable-v2-tag>"
conbench_v2_db_url  = "postgres://conbench_readonly:<secret>@conbench-prod-db.csfk0a0s85z8.us-east-1.rds.amazonaws.com:5432/conbench_prod?sslmode=require&default_transaction_read_only=on&statement_timeout=30s&lock_timeout=2s&idle_in_transaction_session_timeout=30s"

conbench_v2_expose_load_balancer = false
conbench_v2_create_dns_record    = false
```

Do not use `latest`, `dev`, or another mutable image tag. Do not use a
write-enabled database URL for the first UI review pass.

Review the plan before any apply:

```bash
AWS_PROFILE=arrow-conbench terraform plan \
  -var-file=conbench-v2-evaluator.tfvars \
  -target=kubernetes_config_map.conbench_v2 \
  -target=kubernetes_secret.conbench_v2 \
  -target=kubernetes_deployment.conbench_v2 \
  -target=kubernetes_service.conbench_v2
```

The targeted plan is intentional for the first evaluator rollout. The existing
Terraform state owns much more than the evaluator, and this step must not create
pressure to repair unrelated drift or baseline-variable mismatches while people
are waiting for a UI review endpoint.

The plan should create only the `conbench-v2-*` Kubernetes objects while public
exposure and DNS are disabled. It should not change the legacy
`conbench-deployment`, `conbench-service`, `arrow-bci-*` resources, RDS
instances, security groups, or the existing `conbench.arrow-dev.org` record.

## Private Smoke

After an approved apply creates the private evaluator objects, smoke through a
local port-forward:

```bash
AWS_PROFILE=arrow-conbench aws eks update-kubeconfig \
  --region us-east-1 \
  --name conbench-prod \
  --alias arrow-conbench-prod

kubectl --context arrow-conbench-prod \
  -n default \
  port-forward service/conbench-v2-service 18080:80
```

Then check:

```bash
curl -fsS http://127.0.0.1:18080/api/ping
curl -fsS 'http://127.0.0.1:18080/api/runs/recent?page_size=25' >/tmp/conbench-v2-recent.json
```

Also load the dashboard, a representative series page, and a representative CI
report page in a browser. Do not run reporter submissions or token minting
against the read-only production database URL.

## Public Exposure And DNS

Only after private smoke passes, expose the Service as a LoadBalancer:

```hcl
conbench_v2_expose_load_balancer = true
conbench_v2_create_dns_record    = false
```

Review a Terraform plan before applying the exposure change. The plan should
change only `kubernetes_service.conbench_v2`; it should not add Route53 yet.

```bash
AWS_PROFILE=arrow-conbench terraform plan \
  -var-file=conbench-v2-evaluator.tfvars \
  -target=kubernetes_service.conbench_v2
```

After the LoadBalancer exists, collect the evaluator hostname:

```bash
kubectl --context arrow-conbench-prod \
  -n default \
  get svc conbench-v2-service \
  -o jsonpath='{.status.loadBalancer.ingress[0].hostname}'
```

Set:

```hcl
conbench_v2_expose_load_balancer = true
conbench_v2_create_dns_record = true
conbench_v2_elb_dns_name      = "<service-elb-hostname>"
conbench_v2_elb_zone_id       = "Z35SXDOTRQ7X7K"
```

Review a second Terraform plan before applying public DNS. The DNS plan should
only add or update `aws_route53_record.conbench_v2`.

```bash
AWS_PROFILE=arrow-conbench terraform plan \
  -var-file=conbench-v2-evaluator.tfvars \
  -target=aws_route53_record.conbench_v2
```

## Rollback

Rollback is also Terraform-managed. Remove or disable the evaluator in
`conbench-v2-evaluator.tfvars`, review the plan, and apply only after
confirming the plan targets `conbench-v2-*` objects and the optional
`conbench-v2.arrow-dev.org` record. Because the first evaluator uses a
read-only role, no database cleanup should be required.

Never commit `*.tfvars`, database URLs, API tokens, OIDC secrets, or GitHub
tokens.
