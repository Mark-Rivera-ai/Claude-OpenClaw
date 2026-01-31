# OpenClaw AWS Compute Infrastructure (ECS with GPU)

# ============================================================================
# ECS Cluster
# ============================================================================

resource "aws_ecs_cluster" "main" {
  name = "${local.name_prefix}-cluster"

  setting {
    name  = "containerInsights"
    value = var.enable_container_insights ? "enabled" : "disabled"
  }

  tags = {
    Name = "${local.name_prefix}-cluster"
  }
}

resource "aws_ecs_cluster_capacity_providers" "main" {
  cluster_name = aws_ecs_cluster.main.name

  capacity_providers = [aws_ecs_capacity_provider.gpu.name]

  default_capacity_provider_strategy {
    base              = 1
    weight            = 100
    capacity_provider = aws_ecs_capacity_provider.gpu.name
  }
}

# ============================================================================
# ECS Capacity Provider (for GPU instances)
# ============================================================================

resource "aws_ecs_capacity_provider" "gpu" {
  name = "${local.name_prefix}-gpu-capacity-provider"

  auto_scaling_group_provider {
    auto_scaling_group_arn         = aws_autoscaling_group.ecs_gpu.arn
    managed_termination_protection = "ENABLED"

    managed_scaling {
      maximum_scaling_step_size = 2
      minimum_scaling_step_size = 1
      status                    = "ENABLED"
      target_capacity           = 100
    }
  }

  tags = {
    Name = "${local.name_prefix}-gpu-capacity-provider"
  }
}

# ============================================================================
# Launch Template for GPU Instances
# ============================================================================

data "aws_ami" "ecs_gpu" {
  most_recent = true
  owners      = ["amazon"]

  filter {
    name   = "name"
    values = ["amzn2-ami-ecs-gpu-hvm-*-x86_64-ebs"]
  }

  filter {
    name   = "virtualization-type"
    values = ["hvm"]
  }
}

resource "aws_launch_template" "ecs_gpu" {
  name_prefix   = "${local.name_prefix}-gpu-"
  image_id      = data.aws_ami.ecs_gpu.id
  instance_type = var.instance_type

  iam_instance_profile {
    arn = aws_iam_instance_profile.ecs_instance_profile.arn
  }

  network_interfaces {
    associate_public_ip_address = false
    security_groups             = [aws_security_group.ecs_tasks.id]
    delete_on_termination       = true
  }

  block_device_mappings {
    device_name = "/dev/xvda"

    ebs {
      volume_size           = 100
      volume_type           = "gp3"
      delete_on_termination = true
      encrypted             = true
    }
  }

  # Additional storage for model files
  block_device_mappings {
    device_name = "/dev/xvdf"

    ebs {
      volume_size           = 200
      volume_type           = "gp3"
      delete_on_termination = true
      encrypted             = true
    }
  }

  user_data = base64encode(<<-EOF
    #!/bin/bash
    echo "ECS_CLUSTER=${aws_ecs_cluster.main.name}" >> /etc/ecs/ecs.config
    echo "ECS_ENABLE_GPU_SUPPORT=true" >> /etc/ecs/ecs.config
    echo "ECS_NVIDIA_RUNTIME=nvidia" >> /etc/ecs/ecs.config

    # Mount additional volume for models
    mkfs -t xfs /dev/xvdf
    mkdir -p /mnt/models
    mount /dev/xvdf /mnt/models
    echo '/dev/xvdf /mnt/models xfs defaults,nofail 0 2' >> /etc/fstab

    # Install NVIDIA container toolkit (should be included in AMI, but ensure)
    amazon-linux-extras install -y ecs
    systemctl enable --now ecs
  EOF
  )

  tag_specifications {
    resource_type = "instance"
    tags = {
      Name = "${local.name_prefix}-gpu-instance"
    }
  }

  tag_specifications {
    resource_type = "volume"
    tags = {
      Name = "${local.name_prefix}-gpu-volume"
    }
  }

  lifecycle {
    create_before_destroy = true
  }

  tags = {
    Name = "${local.name_prefix}-gpu-launch-template"
  }
}

# ============================================================================
# Auto Scaling Group for GPU Instances
# ============================================================================

resource "aws_autoscaling_group" "ecs_gpu" {
  name_prefix         = "${local.name_prefix}-gpu-asg-"
  vpc_zone_identifier = aws_subnet.private[*].id
  min_size            = var.min_capacity
  max_size            = var.max_capacity
  desired_capacity    = var.desired_capacity

  # Use spot instances if enabled
  mixed_instances_policy {
    instances_distribution {
      on_demand_base_capacity                  = var.enable_spot_instances ? 0 : var.min_capacity
      on_demand_percentage_above_base_capacity = var.enable_spot_instances ? 0 : 100
      spot_allocation_strategy                 = "capacity-optimized"
      spot_max_price                           = var.spot_max_price != "" ? var.spot_max_price : null
    }

    launch_template {
      launch_template_specification {
        launch_template_id = aws_launch_template.ecs_gpu.id
        version            = "$Latest"
      }

      # Override with similar GPU instance types for better spot availability
      dynamic "override" {
        for_each = local.instance_overrides
        content {
          instance_type = override.value
        }
      }
    }
  }

  # Protect instances from scale-in while tasks are running
  protect_from_scale_in = true

  health_check_type         = "EC2"
  health_check_grace_period = 300

  instance_refresh {
    strategy = "Rolling"
    preferences {
      min_healthy_percentage = 50
    }
  }

  tag {
    key                 = "Name"
    value               = "${local.name_prefix}-gpu-asg"
    propagate_at_launch = true
  }

  tag {
    key                 = "AmazonECSManaged"
    value               = "true"
    propagate_at_launch = true
  }

  lifecycle {
    create_before_destroy = true
    ignore_changes        = [desired_capacity]
  }
}

# Instance type overrides for better spot availability
locals {
  instance_overrides = var.instance_type == "g5.xlarge" ? [
    "g5.xlarge",
    "g5.2xlarge",
    "g4dn.xlarge",
    "g4dn.2xlarge"
  ] : var.instance_type == "g4dn.xlarge" ? [
    "g4dn.xlarge",
    "g4dn.2xlarge",
    "g5.xlarge"
  ] : [var.instance_type]
}

# ============================================================================
# Application Load Balancer
# ============================================================================

resource "aws_lb" "main" {
  name               = "${local.name_prefix}-alb"
  internal           = false
  load_balancer_type = "application"
  security_groups    = [aws_security_group.alb.id]
  subnets            = aws_subnet.public[*].id

  enable_deletion_protection = var.environment == "prod" ? true : false

  tags = {
    Name = "${local.name_prefix}-alb"
  }
}

resource "aws_lb_target_group" "openclaw" {
  name        = "${local.name_prefix}-tg"
  port        = var.app_port
  protocol    = "HTTP"
  vpc_id      = aws_vpc.main.id
  target_type = "ip"

  health_check {
    enabled             = true
    healthy_threshold   = 2
    interval            = 30
    matcher             = "200"
    path                = var.health_check_path
    port                = "traffic-port"
    protocol            = "HTTP"
    timeout             = 10
    unhealthy_threshold = 3
  }

  tags = {
    Name = "${local.name_prefix}-tg"
  }
}

# HTTP Listener
resource "aws_lb_listener" "http" {
  load_balancer_arn = aws_lb.main.arn
  port              = 80
  protocol          = "HTTP"

  default_action {
    type = var.ssl_certificate_arn != "" ? "redirect" : "forward"

    dynamic "redirect" {
      for_each = var.ssl_certificate_arn != "" ? [1] : []
      content {
        port        = "443"
        protocol    = "HTTPS"
        status_code = "HTTP_301"
      }
    }

    dynamic "forward" {
      for_each = var.ssl_certificate_arn == "" ? [1] : []
      content {
        target_group {
          arn = aws_lb_target_group.openclaw.arn
        }
      }
    }
  }
}

# HTTPS Listener (only if certificate is provided)
resource "aws_lb_listener" "https" {
  count = var.ssl_certificate_arn != "" ? 1 : 0

  load_balancer_arn = aws_lb.main.arn
  port              = 443
  protocol          = "HTTPS"
  ssl_policy        = "ELBSecurityPolicy-TLS13-1-2-2021-06"
  certificate_arn   = var.ssl_certificate_arn

  default_action {
    type             = "forward"
    target_group_arn = aws_lb_target_group.openclaw.arn
  }
}
