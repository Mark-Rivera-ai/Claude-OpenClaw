# OpenClaw GCP Infrastructure

This directory will contain the Google Cloud Platform infrastructure configuration for OpenClaw.

## Status: Planned

GCP support is planned for a future release. The infrastructure will include:

- **Cloud Run** with GPU support (or GKE with GPU node pools)
- **VPC** for network isolation
- **Artifact Registry** for Docker images
- **Cloud Storage** for model storage
- **Cloud Logging/Monitoring** for observability

## Planned Configuration

```hcl
# Example structure (to be implemented)
resource "google_cloud_run_v2_service" "openclaw" {
  name     = "openclaw-${var.environment}"
  location = var.region

  template {
    containers {
      image = "${var.region}-docker.pkg.dev/${var.project_id}/openclaw/openclaw:latest"

      resources {
        limits = {
          cpu    = "4"
          memory = "16Gi"
          "nvidia.com/gpu" = "1"
        }
      }

      ports {
        container_port = 8080
      }

      env {
        name  = "LLAMA_MODEL"
        value = var.llama_model
      }
    }

    scaling {
      min_instance_count = 1
      max_instance_count = 10
    }
  }
}
```

## GPU Options

| Accelerator | VRAM | Use Case |
|-------------|------|----------|
| nvidia-tesla-t4 | 16GB | 8B models, cost-effective |
| nvidia-l4 | 24GB | 8B models, newer |
| nvidia-tesla-a100 | 40/80GB | 70B+ models |

## GKE Alternative

For larger deployments, GKE with GPU node pools may be preferred:

```hcl
resource "google_container_node_pool" "gpu" {
  name       = "gpu-pool"
  cluster    = google_container_cluster.main.name
  node_count = 1

  node_config {
    machine_type = "n1-standard-4"

    guest_accelerator {
      type  = "nvidia-tesla-t4"
      count = 1
    }
  }
}
```

## Contributing

To contribute GCP support:

1. Create the Terraform configuration following the AWS structure
2. Ensure parity with AWS features where applicable
3. Document GCP-specific considerations
4. Test thoroughly before submitting a PR
