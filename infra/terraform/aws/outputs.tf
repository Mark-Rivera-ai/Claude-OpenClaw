# OpenClaw AWS Infrastructure Outputs

# ============================================================================
# Network Outputs
# ============================================================================

output "vpc_id" {
  description = "ID of the VPC"
  value       = aws_vpc.main.id
}

output "public_subnet_ids" {
  description = "IDs of the public subnets"
  value       = aws_subnet.public[*].id
}

output "private_subnet_ids" {
  description = "IDs of the private subnets"
  value       = aws_subnet.private[*].id
}

# ============================================================================
# Load Balancer Outputs
# ============================================================================

output "alb_dns_name" {
  description = "DNS name of the Application Load Balancer"
  value       = aws_lb.main.dns_name
}

output "alb_zone_id" {
  description = "Zone ID of the Application Load Balancer"
  value       = aws_lb.main.zone_id
}

output "application_url" {
  description = "URL to access the OpenClaw application"
  value       = "http://${aws_lb.main.dns_name}"
}

# ============================================================================
# ECS Outputs
# ============================================================================

output "ecs_cluster_name" {
  description = "Name of the ECS cluster"
  value       = aws_ecs_cluster.main.name
}

output "ecs_cluster_arn" {
  description = "ARN of the ECS cluster"
  value       = aws_ecs_cluster.main.arn
}

output "ecs_service_name" {
  description = "Name of the ECS service"
  value       = aws_ecs_service.openclaw.name
}

# ============================================================================
# ECR Outputs
# ============================================================================

output "ecr_repository_url" {
  description = "URL of the ECR repository"
  value       = aws_ecr_repository.openclaw.repository_url
}

output "ecr_repository_arn" {
  description = "ARN of the ECR repository"
  value       = aws_ecr_repository.openclaw.arn
}

# ============================================================================
# IAM Outputs
# ============================================================================

output "ecs_task_role_arn" {
  description = "ARN of the ECS task IAM role"
  value       = aws_iam_role.ecs_task_role.arn
}

output "ecs_execution_role_arn" {
  description = "ARN of the ECS execution IAM role"
  value       = aws_iam_role.ecs_execution_role.arn
}

# ============================================================================
# Monitoring Outputs
# ============================================================================

output "cloudwatch_log_group" {
  description = "Name of the CloudWatch log group"
  value       = aws_cloudwatch_log_group.openclaw.name
}

# ============================================================================
# Deployment Information
# ============================================================================

output "deployment_info" {
  description = "Summary of deployment information"
  value = {
    environment    = var.environment
    region         = var.aws_region
    instance_type  = var.instance_type
    llama_model    = var.llama_model
    spot_enabled   = var.enable_spot_instances
    application_url = "http://${aws_lb.main.dns_name}"
  }
}

output "next_steps" {
  description = "Next steps after infrastructure deployment"
  value       = <<-EOT

    Infrastructure deployed successfully!

    Next steps:
    1. Build and push the Docker image:
       ./infra/scripts/deploy.sh build

    2. Deploy the application:
       ./infra/scripts/deploy.sh deploy

    3. Access the application at:
       ${aws_lb.main.dns_name}

    4. View logs:
       aws logs tail ${aws_cloudwatch_log_group.openclaw.name} --follow
  EOT
}
