# OpenClaw AWS Infrastructure
# Main configuration file

provider "aws" {
  region = var.aws_region

  default_tags {
    tags = {
      Project     = "OpenClaw"
      Environment = var.environment
      ManagedBy   = "Terraform"
      Repository  = "Claude-OpenClaw"
    }
  }
}

# Random suffix for unique resource names
resource "random_id" "suffix" {
  byte_length = 4
}

locals {
  name_prefix = "openclaw-${var.environment}"
  common_tags = {
    Project     = "OpenClaw"
    Environment = var.environment
  }
}

# Data sources
data "aws_availability_zones" "available" {
  state = "available"
}

data "aws_caller_identity" "current" {}

data "aws_region" "current" {}
