#!/bin/bash
# OpenClaw Deployment Script
# Usage: ./deploy.sh [command] [options]

set -euo pipefail

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Default values
ENVIRONMENT="${ENVIRONMENT:-dev}"
AWS_REGION="${AWS_REGION:-us-east-1}"
IMAGE_TAG="${IMAGE_TAG:-latest}"

# Get script directory
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "${SCRIPT_DIR}/../.." && pwd)"
TERRAFORM_DIR="${PROJECT_ROOT}/infra/terraform/aws"
APP_DIR="${PROJECT_ROOT}/app"

# Functions
log_info() {
    echo -e "${GREEN}[INFO]${NC} $1"
}

log_warn() {
    echo -e "${YELLOW}[WARN]${NC} $1"
}

log_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

check_dependencies() {
    log_info "Checking dependencies..."

    local deps=("aws" "terraform" "docker")
    for dep in "${deps[@]}"; do
        if ! command -v "$dep" &> /dev/null; then
            log_error "$dep is required but not installed"
            exit 1
        fi
    done

    log_info "All dependencies found"
}

get_ecr_url() {
    cd "${TERRAFORM_DIR}"
    terraform output -raw ecr_repository_url 2>/dev/null || echo ""
}

get_ecs_cluster() {
    cd "${TERRAFORM_DIR}"
    terraform output -raw ecs_cluster_name 2>/dev/null || echo ""
}

get_ecs_service() {
    cd "${TERRAFORM_DIR}"
    terraform output -raw ecs_service_name 2>/dev/null || echo ""
}

# Commands
cmd_init() {
    log_info "Initializing Terraform..."
    cd "${TERRAFORM_DIR}"
    terraform init
    log_info "Terraform initialized"
}

cmd_plan() {
    log_info "Planning infrastructure changes..."
    cd "${TERRAFORM_DIR}"
    terraform plan -var="environment=${ENVIRONMENT}"
}

cmd_apply() {
    log_info "Applying infrastructure changes..."
    cd "${TERRAFORM_DIR}"
    terraform apply -var="environment=${ENVIRONMENT}"
    log_info "Infrastructure deployed"
}

cmd_destroy() {
    log_warn "This will destroy all infrastructure!"
    read -p "Are you sure? (yes/no): " confirm
    if [[ "$confirm" == "yes" ]]; then
        cd "${TERRAFORM_DIR}"
        terraform destroy -var="environment=${ENVIRONMENT}"
    else
        log_info "Cancelled"
    fi
}

cmd_build() {
    log_info "Building Docker image..."

    local ecr_url=$(get_ecr_url)
    if [[ -z "$ecr_url" ]]; then
        log_error "ECR repository URL not found. Run 'deploy.sh apply' first."
        exit 1
    fi

    cd "${APP_DIR}"

    # Build the image
    docker build -t openclaw:${IMAGE_TAG} .
    docker tag openclaw:${IMAGE_TAG} ${ecr_url}:${IMAGE_TAG}

    log_info "Docker image built: ${ecr_url}:${IMAGE_TAG}"
}

cmd_push() {
    log_info "Pushing Docker image to ECR..."

    local ecr_url=$(get_ecr_url)
    if [[ -z "$ecr_url" ]]; then
        log_error "ECR repository URL not found. Run 'deploy.sh apply' first."
        exit 1
    fi

    # Login to ECR
    local account_id=$(aws sts get-caller-identity --query Account --output text)
    aws ecr get-login-password --region ${AWS_REGION} | \
        docker login --username AWS --password-stdin ${account_id}.dkr.ecr.${AWS_REGION}.amazonaws.com

    # Push the image
    docker push ${ecr_url}:${IMAGE_TAG}

    log_info "Docker image pushed to ECR"
}

cmd_deploy() {
    log_info "Deploying application..."

    local cluster=$(get_ecs_cluster)
    local service=$(get_ecs_service)

    if [[ -z "$cluster" ]] || [[ -z "$service" ]]; then
        log_error "ECS cluster/service not found. Run 'deploy.sh apply' first."
        exit 1
    fi

    # Force new deployment
    aws ecs update-service \
        --cluster "$cluster" \
        --service "$service" \
        --force-new-deployment \
        --region ${AWS_REGION}

    log_info "Deployment triggered. Use 'deploy.sh status' to monitor."
}

cmd_status() {
    log_info "Checking deployment status..."

    local cluster=$(get_ecs_cluster)
    local service=$(get_ecs_service)

    if [[ -z "$cluster" ]] || [[ -z "$service" ]]; then
        log_error "ECS cluster/service not found."
        exit 1
    fi

    aws ecs describe-services \
        --cluster "$cluster" \
        --services "$service" \
        --region ${AWS_REGION} \
        --query 'services[0].{Status:status,Running:runningCount,Desired:desiredCount,Pending:pendingCount}'
}

cmd_logs() {
    log_info "Fetching logs..."

    local log_group="/ecs/openclaw-${ENVIRONMENT}"
    aws logs tail "$log_group" --follow --region ${AWS_REGION}
}

cmd_output() {
    log_info "Terraform outputs..."
    cd "${TERRAFORM_DIR}"
    terraform output
}

cmd_help() {
    cat << EOF
OpenClaw Deployment Script

Usage: ./deploy.sh [command] [options]

Commands:
  init      Initialize Terraform
  plan      Show infrastructure changes
  apply     Deploy infrastructure
  destroy   Destroy infrastructure
  build     Build Docker image
  push      Push Docker image to ECR
  deploy    Deploy application to ECS
  status    Check deployment status
  logs      View application logs
  output    Show Terraform outputs
  help      Show this help message

Environment Variables:
  ENVIRONMENT   Deployment environment (default: dev)
  AWS_REGION    AWS region (default: us-east-1)
  IMAGE_TAG     Docker image tag (default: latest)

Examples:
  ./deploy.sh init
  ./deploy.sh apply
  ENVIRONMENT=prod ./deploy.sh build
  ./deploy.sh push
  ./deploy.sh deploy

EOF
}

# Main
main() {
    local command="${1:-help}"

    check_dependencies

    case "$command" in
        init)    cmd_init ;;
        plan)    cmd_plan ;;
        apply)   cmd_apply ;;
        destroy) cmd_destroy ;;
        build)   cmd_build ;;
        push)    cmd_push ;;
        deploy)  cmd_deploy ;;
        status)  cmd_status ;;
        logs)    cmd_logs ;;
        output)  cmd_output ;;
        help)    cmd_help ;;
        *)
            log_error "Unknown command: $command"
            cmd_help
            exit 1
            ;;
    esac
}

main "$@"
