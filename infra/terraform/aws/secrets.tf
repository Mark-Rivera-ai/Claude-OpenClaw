# OpenClaw AWS Secrets Manager Configuration
# Security-hardened secret storage for sensitive credentials

# ============================================================================
# Anthropic API Key Secret
# ============================================================================

resource "aws_secretsmanager_secret" "anthropic_api_key" {
  name        = "${var.environment}-openclaw-anthropic-key"
  description = "Anthropic API key for OpenClaw ${var.environment} environment"

  # Enable automatic recovery window (minimum 7 days, set to 30 for prod safety)
  recovery_window_in_days = var.environment == "prod" ? 30 : 7

  tags = {
    Name        = "${var.environment}-openclaw-anthropic-key"
    Environment = var.environment
    Purpose     = "anthropic-api-credentials"
  }
}

# Placeholder secret version - actual value should be set via AWS CLI or Console
# Example: aws secretsmanager put-secret-value --secret-id dev-openclaw-anthropic-key --secret-string "sk-ant-..."
resource "aws_secretsmanager_secret_version" "anthropic_api_key" {
  secret_id = aws_secretsmanager_secret.anthropic_api_key.id

  # Placeholder value - MUST be updated after deployment
  secret_string = jsonencode({
    ANTHROPIC_API_KEY = "REPLACE_WITH_ACTUAL_API_KEY"
  })

  lifecycle {
    ignore_changes = [secret_string]
  }
}

# ============================================================================
# IAM Policy for ECS Tasks to Access Anthropic Secret
# ============================================================================

resource "aws_iam_policy" "secrets_access" {
  name        = "${local.name_prefix}-secrets-access"
  description = "Allows ECS tasks to read OpenClaw secrets from Secrets Manager"

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Sid    = "GetAnthropicSecret"
        Effect = "Allow"
        Action = [
          "secretsmanager:GetSecretValue"
        ]
        Resource = [
          aws_secretsmanager_secret.anthropic_api_key.arn
        ]
      },
      {
        Sid    = "DecryptSecret"
        Effect = "Allow"
        Action = [
          "kms:Decrypt"
        ]
        Resource = "*"
        Condition = {
          StringEquals = {
            "kms:ViaService" = "secretsmanager.${var.aws_region}.amazonaws.com"
          }
        }
      }
    ]
  })

  tags = {
    Name = "${local.name_prefix}-secrets-access"
  }
}

# Attach the secrets policy to the ECS execution role
resource "aws_iam_role_policy_attachment" "ecs_execution_secrets" {
  role       = aws_iam_role.ecs_execution_role.name
  policy_arn = aws_iam_policy.secrets_access.arn
}

# Attach the secrets policy to the ECS task role (for runtime access if needed)
resource "aws_iam_role_policy_attachment" "ecs_task_secrets" {
  role       = aws_iam_role.ecs_task_role.name
  policy_arn = aws_iam_policy.secrets_access.arn
}
