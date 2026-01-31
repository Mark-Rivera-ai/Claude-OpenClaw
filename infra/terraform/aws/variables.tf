# OpenClaw AWS Infrastructure Variables

# ============================================================================
# General Configuration
# ============================================================================

variable "environment" {
  description = "Deployment environment (dev, staging, prod)"
  type        = string
  default     = "dev"

  validation {
    condition     = contains(["dev", "staging", "prod"], var.environment)
    error_message = "Environment must be dev, staging, or prod."
  }
}

variable "aws_region" {
  description = "AWS region for deployment"
  type        = string
  default     = "us-east-1"
}

# ============================================================================
# Network Configuration
# ============================================================================

variable "vpc_cidr" {
  description = "CIDR block for the VPC"
  type        = string
  default     = "10.0.0.0/16"
}

variable "availability_zones_count" {
  description = "Number of availability zones to use"
  type        = number
  default     = 2
}

# ============================================================================
# Compute Configuration
# ============================================================================

variable "instance_type" {
  description = "EC2 instance type for GPU compute (must have GPU for Llama)"
  type        = string
  default     = "g5.xlarge"

  validation {
    condition = contains([
      "g4dn.xlarge", "g4dn.2xlarge", "g4dn.4xlarge", "g4dn.8xlarge", "g4dn.12xlarge", "g4dn.16xlarge",
      "g5.xlarge", "g5.2xlarge", "g5.4xlarge", "g5.8xlarge", "g5.12xlarge", "g5.16xlarge", "g5.24xlarge", "g5.48xlarge",
      "p3.2xlarge", "p3.8xlarge", "p3.16xlarge",
      "p4d.24xlarge"
    ], var.instance_type)
    error_message = "Instance type must be a GPU instance (g4dn, g5, p3, or p4d series)."
  }
}

variable "enable_spot_instances" {
  description = "Use spot instances for cost savings (may be interrupted)"
  type        = bool
  default     = true
}

variable "spot_max_price" {
  description = "Maximum hourly price for spot instances (empty = on-demand price)"
  type        = string
  default     = ""
}

variable "min_capacity" {
  description = "Minimum number of instances in the cluster"
  type        = number
  default     = 1
}

variable "max_capacity" {
  description = "Maximum number of instances in the cluster"
  type        = number
  default     = 3
}

variable "desired_capacity" {
  description = "Desired number of instances in the cluster"
  type        = number
  default     = 1
}

# ============================================================================
# Llama Model Configuration
# ============================================================================

variable "llama_model" {
  description = "Llama model variant to deploy"
  type        = string
  default     = "llama-3.1-8b"

  validation {
    condition = contains([
      "llama-3.2-1b",
      "llama-3.2-3b",
      "llama-3.1-8b",
      "llama-3.1-70b",
      "llama-3.1-405b"
    ], var.llama_model)
    error_message = "Unsupported Llama model variant."
  }
}

variable "model_quantization" {
  description = "Model quantization level (none, int8, int4)"
  type        = string
  default     = "none"

  validation {
    condition     = contains(["none", "int8", "int4"], var.model_quantization)
    error_message = "Quantization must be none, int8, or int4."
  }
}

# ============================================================================
# Application Configuration
# ============================================================================

variable "app_port" {
  description = "Port the OpenClaw application listens on"
  type        = number
  default     = 8080
}

variable "health_check_path" {
  description = "Path for health check endpoint"
  type        = string
  default     = "/health"
}

variable "container_cpu" {
  description = "CPU units for the container (1024 = 1 vCPU)"
  type        = number
  default     = 2048
}

variable "container_memory" {
  description = "Memory for the container in MB"
  type        = number
  default     = 8192
}

# ============================================================================
# Security Configuration
# ============================================================================

variable "allowed_cidr_blocks" {
  description = "CIDR blocks allowed to access the application"
  type        = list(string)
  default     = ["0.0.0.0/0"]
}

variable "enable_waf" {
  description = "Enable AWS WAF for the Application Load Balancer"
  type        = bool
  default     = false
}

variable "ssl_certificate_arn" {
  description = "ARN of ACM certificate for HTTPS (optional)"
  type        = string
  default     = ""
}

# ============================================================================
# Monitoring Configuration
# ============================================================================

variable "enable_container_insights" {
  description = "Enable CloudWatch Container Insights"
  type        = bool
  default     = true
}

variable "log_retention_days" {
  description = "CloudWatch log retention in days"
  type        = number
  default     = 30
}

variable "alarm_email" {
  description = "Email address for CloudWatch alarms (optional)"
  type        = string
  default     = ""
}
