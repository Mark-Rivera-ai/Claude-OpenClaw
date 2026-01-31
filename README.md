# OpenClaw (ClawdBot) Infrastructure

Infrastructure as Code (IaC) for deploying OpenClaw - an AI-powered bot running on Llama LLM.

## Architecture Overview

OpenClaw runs on self-hosted Llama models deployed on GPU-enabled cloud infrastructure. The architecture is designed to be cloud-agnostic with initial support for AWS.

```
┌─────────────────────────────────────────────────────────────────┐
│                         AWS Cloud                                │
│  ┌───────────────────────────────────────────────────────────┐  │
│  │                        VPC                                 │  │
│  │  ┌─────────────────┐     ┌─────────────────────────────┐  │  │
│  │  │  Public Subnet  │     │      Private Subnet         │  │  │
│  │  │  ┌───────────┐  │     │  ┌───────────────────────┐  │  │  │
│  │  │  │    ALB    │──┼─────┼─▶│   ECS Cluster (GPU)   │  │  │  │
│  │  │  └───────────┘  │     │  │  ┌─────────────────┐  │  │  │  │
│  │  │                 │     │  │  │  OpenClaw App   │  │  │  │  │
│  │  │  ┌───────────┐  │     │  │  │  + Llama Model  │  │  │  │  │
│  │  │  │  NAT GW   │  │     │  │  └─────────────────┘  │  │  │  │
│  │  │  └───────────┘  │     │  └───────────────────────┘  │  │  │
│  │  └─────────────────┘     └─────────────────────────────┘  │  │
│  └───────────────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────────┘
```

## Project Structure

```
.
├── infra/
│   ├── terraform/
│   │   ├── aws/              # AWS infrastructure
│   │   ├── azure/            # Azure infrastructure (future)
│   │   ├── gcp/              # GCP infrastructure (future)
│   │   └── modules/          # Shared Terraform modules
│   └── scripts/              # Deployment scripts
├── app/
│   ├── Dockerfile            # OpenClaw container image
│   ├── docker-compose.yml    # Local development
│   └── src/                  # Application source (placeholder)
└── README.md
```

## Cloud Support

| Cloud Provider | Status | Description |
|---------------|--------|-------------|
| AWS | ✅ Ready | Full infrastructure with ECS on GPU instances |
| Azure | 🔜 Planned | Azure Container Instances with GPU |
| GCP | 🔜 Planned | Cloud Run with GPU or GKE |

## Prerequisites

- [Terraform](https://www.terraform.io/downloads) >= 1.5.0
- [AWS CLI](https://aws.amazon.com/cli/) configured with appropriate credentials
- [Docker](https://www.docker.com/) for local development
- GPU quota approved in your AWS account for g5/g4dn instances

## Quick Start

### 1. Configure AWS Credentials

```bash
aws configure
# Or set environment variables:
export AWS_ACCESS_KEY_ID="your-access-key"
export AWS_SECRET_ACCESS_KEY="your-secret-key"
export AWS_DEFAULT_REGION="us-east-1"
```

### 2. Deploy Infrastructure

```bash
cd infra/terraform/aws

# Initialize Terraform
terraform init

# Review the plan
terraform plan -var="environment=dev"

# Apply the infrastructure
terraform apply -var="environment=dev"
```

### 3. Deploy OpenClaw Application

```bash
# Build and push Docker image
./infra/scripts/deploy.sh build

# Deploy to ECS
./infra/scripts/deploy.sh deploy
```

## Configuration

### Terraform Variables

| Variable | Description | Default |
|----------|-------------|---------|
| `environment` | Deployment environment (dev/staging/prod) | `dev` |
| `aws_region` | AWS region for deployment | `us-east-1` |
| `instance_type` | EC2 instance type for GPU compute | `g5.xlarge` |
| `llama_model` | Llama model variant to deploy | `llama-3.1-8b` |
| `enable_spot` | Use spot instances for cost savings | `true` |

### Llama Model Options

| Model | VRAM Required | Instance Type |
|-------|--------------|---------------|
| Llama 3.1 8B | 16GB | g5.xlarge |
| Llama 3.1 70B | 140GB | g5.48xlarge / p4d.24xlarge |
| Llama 3.2 3B | 8GB | g4dn.xlarge |

## Cost Optimization

- **Spot Instances**: Enabled by default for up to 90% cost savings
- **Auto-scaling**: Scales down during low usage periods
- **Right-sizing**: Choose the smallest instance that fits your model

## Security

- All resources deployed in private subnets
- Application Load Balancer in public subnet with HTTPS
- IAM roles with least-privilege access
- Security groups with minimal required ports
- Secrets managed via AWS Secrets Manager

## License

MIT License - See LICENSE file for details
