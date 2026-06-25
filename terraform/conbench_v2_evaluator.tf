# Conbench v2 evaluator resources.
#
# These resources are disabled by default. Enable them only for a reviewed
# Terraform plan that stands up a parallel evaluator beside the legacy
# Python/Flask Conbench deployment.

resource "kubernetes_config_map" "conbench_v2" {
  count = var.conbench_v2_enabled ? 1 : 0

  metadata {
    name      = "conbench-v2-config"
    namespace = var.conbench_v2_namespace
    labels = {
      app = "conbench-v2"
    }
  }

  data = merge(
    {
      CONBENCH_ADDR              = var.conbench_v2_addr
      CONBENCH_INTENDED_BASE_URL = var.conbench_v2_public_url
    },
    var.conbench_v2_github_timeout != "" ? {
      CONBENCH_GITHUB_TIMEOUT = var.conbench_v2_github_timeout
    } : {}
  )

  depends_on = [
    aws_eks_cluster.conbench,
    aws_eks_node_group.conbench
  ]
}

resource "kubernetes_secret" "conbench_v2" {
  count = var.conbench_v2_enabled ? 1 : 0

  metadata {
    name      = "conbench-v2-secret"
    namespace = var.conbench_v2_namespace
    labels = {
      app = "conbench-v2"
    }
  }

  data = merge(
    {
      CONBENCH_DB_URL = var.conbench_v2_db_url
    },
    var.conbench_v2_api_token != "" ? {
      CONBENCH_API_TOKEN = var.conbench_v2_api_token
    } : {},
    var.conbench_v2_github_api_token != "" ? {
      GITHUB_API_TOKEN = var.conbench_v2_github_api_token
    } : {},
    var.conbench_v2_oidc_issuer_url != "" ? {
      CONBENCH_OIDC_ISSUER_URL = var.conbench_v2_oidc_issuer_url
    } : {},
    var.conbench_v2_oidc_client_id != "" ? {
      CONBENCH_OIDC_CLIENT_ID = var.conbench_v2_oidc_client_id
    } : {},
    var.conbench_v2_oidc_client_secret != "" ? {
      CONBENCH_OIDC_CLIENT_SECRET = var.conbench_v2_oidc_client_secret
    } : {},
    var.conbench_v2_session_secret != "" ? {
      CONBENCH_SESSION_SECRET = var.conbench_v2_session_secret
    } : {}
  )

  depends_on = [
    aws_eks_cluster.conbench,
    aws_eks_node_group.conbench
  ]
}

resource "kubernetes_deployment" "conbench_v2" {
  count = var.conbench_v2_enabled ? 1 : 0

  metadata {
    name      = "conbench-v2-deployment"
    namespace = var.conbench_v2_namespace
    labels = {
      app = "conbench-v2"
    }
  }

  spec {
    replicas = var.conbench_v2_replicas

    selector {
      match_labels = {
        app = "conbench-v2"
      }
    }

    strategy {
      type = "RollingUpdate"
      rolling_update {
        max_surge       = "25%"
        max_unavailable = "25%"
      }
    }

    template {
      metadata {
        labels = {
          app = "conbench-v2"
        }
      }

      spec {
        container {
          name              = "conbench-v2"
          image             = var.conbench_v2_image
          image_pull_policy = "Always"

          port {
            container_port = 8080
            name           = "http"
          }

          env_from {
            config_map_ref {
              name = kubernetes_config_map.conbench_v2[0].metadata[0].name
            }
          }

          env_from {
            secret_ref {
              name = kubernetes_secret.conbench_v2[0].metadata[0].name
            }
          }

          resources {
            requests = {
              cpu    = "250m"
              memory = "512Mi"
            }
            limits = {
              memory = "1Gi"
            }
          }

          startup_probe {
            http_get {
              path = "/api/ping"
              port = "http"
            }
            failure_threshold = 30
            period_seconds    = 2
            timeout_seconds   = 5
          }

          readiness_probe {
            http_get {
              path = "/api/ping"
              port = "http"
            }
            failure_threshold = 3
            period_seconds    = 10
            success_threshold = 1
            timeout_seconds   = 5
          }

          liveness_probe {
            http_get {
              path = "/api/ping"
              port = "http"
            }
            failure_threshold = 3
            period_seconds    = 30
            timeout_seconds   = 5
          }
        }

        termination_grace_period_seconds = 60
      }
    }
  }

  depends_on = [
    kubernetes_config_map.conbench_v2,
    kubernetes_secret.conbench_v2
  ]
}

resource "kubernetes_service" "conbench_v2" {
  count = var.conbench_v2_enabled ? 1 : 0

  metadata {
    name      = "conbench-v2-service"
    namespace = var.conbench_v2_namespace
    annotations = {
      "service.beta.kubernetes.io/aws-load-balancer-backend-protocol" = "http"
      "service.beta.kubernetes.io/aws-load-balancer-ssl-cert"         = aws_acm_certificate.arrow_dev.arn
      "service.beta.kubernetes.io/aws-load-balancer-ssl-ports"        = "443"
    }
    labels = {
      app = "conbench-v2"
    }
  }

  spec {
    type = var.conbench_v2_expose_load_balancer ? "LoadBalancer" : "ClusterIP"

    selector = {
      app = "conbench-v2"
    }

    port {
      name        = "http"
      port        = 80
      target_port = 8080
      protocol    = "TCP"
    }

    port {
      name        = "https"
      port        = 443
      target_port = 8080
      protocol    = "TCP"
    }
  }

  depends_on = [
    kubernetes_deployment.conbench_v2,
    aws_acm_certificate_validation.arrow_dev
  ]
}

resource "aws_route53_record" "conbench_v2" {
  count = var.conbench_v2_enabled && var.conbench_v2_expose_load_balancer && var.conbench_v2_create_dns_record ? 1 : 0

  zone_id = data.aws_route53_zone.arrow_dev.zone_id
  name    = var.conbench_v2_dns_name
  type    = "A"

  alias {
    name                   = var.conbench_v2_elb_dns_name
    zone_id                = var.conbench_v2_elb_zone_id
    evaluate_target_health = true
  }

  lifecycle {
    create_before_destroy = true
  }

  depends_on = [
    kubernetes_service.conbench_v2
  ]
}
