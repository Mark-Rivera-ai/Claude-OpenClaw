# OpenClaw Azure Infrastructure

This directory will contain the Azure infrastructure configuration for OpenClaw.

## Status: Planned

Azure support is planned for a future release. The infrastructure will include:

- **Azure Container Instances (ACI)** with GPU support
- **Azure Virtual Network** for network isolation
- **Azure Container Registry** for Docker images
- **Azure Blob Storage** for model storage
- **Azure Monitor** for logging and metrics

## Planned Configuration

```hcl
# Example structure (to be implemented)
resource "azurerm_container_group" "openclaw" {
  name                = "openclaw-${var.environment}"
  location            = azurerm_resource_group.main.location
  resource_group_name = azurerm_resource_group.main.name
  os_type             = "Linux"

  container {
    name   = "openclaw"
    image  = "${azurerm_container_registry.main.login_server}/openclaw:latest"
    cpu    = "4"
    memory = "16"

    gpu {
      count = 1
      sku   = "K80"  # or "P100", "V100"
    }

    ports {
      port     = 8080
      protocol = "TCP"
    }
  }
}
```

## GPU Instance Options

| SKU | GPU | VRAM | Use Case |
|-----|-----|------|----------|
| K80 | NVIDIA K80 | 12GB | Small models |
| P100 | NVIDIA P100 | 16GB | 8B models |
| V100 | NVIDIA V100 | 16GB | 8B-70B models |

## Contributing

To contribute Azure support:

1. Create the Terraform configuration following the AWS structure
2. Ensure parity with AWS features where applicable
3. Document Azure-specific considerations
4. Test thoroughly before submitting a PR
