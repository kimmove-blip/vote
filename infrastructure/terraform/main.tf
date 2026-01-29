# Terraform Configuration for Blockchain Voting System
# AWS Infrastructure

terraform {
  required_version = ">= 1.0.0"

  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.0"
    }
    kubernetes = {
      source  = "hashicorp/kubernetes"
      version = "~> 2.23"
    }
  }

  backend "s3" {
    bucket         = "voting-system-terraform-state"
    key            = "production/terraform.tfstate"
    region         = "ap-northeast-2"
    encrypt        = true
    dynamodb_table = "terraform-locks"
  }
}

provider "aws" {
  region = var.aws_region

  default_tags {
    tags = {
      Project     = "BlockchainVoting"
      Environment = var.environment
      ManagedBy   = "Terraform"
    }
  }
}

# =============================================================================
# Variables
# =============================================================================

variable "aws_region" {
  description = "AWS region"
  type        = string
  default     = "ap-northeast-2"
}

variable "environment" {
  description = "Environment name"
  type        = string
  default     = "production"
}

variable "vpc_cidr" {
  description = "VPC CIDR block"
  type        = string
  default     = "10.0.0.0/16"
}

variable "availability_zones" {
  description = "Availability zones"
  type        = list(string)
  default     = ["ap-northeast-2a", "ap-northeast-2b", "ap-northeast-2c"]
}

# =============================================================================
# VPC and Networking
# =============================================================================

module "vpc" {
  source  = "terraform-aws-modules/vpc/aws"
  version = "~> 5.0"

  name = "voting-vpc-${var.environment}"
  cidr = var.vpc_cidr

  azs             = var.availability_zones
  private_subnets = ["10.0.1.0/24", "10.0.2.0/24", "10.0.3.0/24"]
  public_subnets  = ["10.0.101.0/24", "10.0.102.0/24", "10.0.103.0/24"]

  enable_nat_gateway     = true
  single_nat_gateway     = false
  one_nat_gateway_per_az = true

  enable_dns_hostnames = true
  enable_dns_support   = true

  # VPC Flow Logs
  enable_flow_log                      = true
  create_flow_log_cloudwatch_log_group = true
  create_flow_log_cloudwatch_iam_role  = true

  tags = {
    "kubernetes.io/cluster/voting-cluster" = "shared"
  }

  public_subnet_tags = {
    "kubernetes.io/cluster/voting-cluster" = "shared"
    "kubernetes.io/role/elb"               = "1"
  }

  private_subnet_tags = {
    "kubernetes.io/cluster/voting-cluster" = "shared"
    "kubernetes.io/role/internal-elb"      = "1"
  }
}

# =============================================================================
# EKS Cluster
# =============================================================================

module "eks" {
  source  = "terraform-aws-modules/eks/aws"
  version = "~> 19.0"

  cluster_name    = "voting-cluster-${var.environment}"
  cluster_version = "1.28"

  cluster_endpoint_public_access  = true
  cluster_endpoint_private_access = true

  vpc_id     = module.vpc.vpc_id
  subnet_ids = module.vpc.private_subnets

  # Cluster encryption
  cluster_encryption_config = {
    provider_key_arn = aws_kms_key.eks.arn
    resources        = ["secrets"]
  }

  # Managed node groups
  eks_managed_node_groups = {
    # Application nodes
    app = {
      name           = "app-nodes"
      instance_types = ["m5.xlarge"]
      min_size       = 3
      max_size       = 10
      desired_size   = 5

      labels = {
        workload = "application"
      }
    }

    # Blockchain nodes
    blockchain = {
      name           = "blockchain-nodes"
      instance_types = ["m5.2xlarge"]
      min_size       = 6
      max_size       = 12
      desired_size   = 6

      labels = {
        workload = "blockchain"
      }

      taints = [
        {
          key    = "dedicated"
          value  = "blockchain"
          effect = "NO_SCHEDULE"
        }
      ]
    }
  }

  # Fargate profiles for serverless workloads
  fargate_profiles = {
    default = {
      name = "default"
      selectors = [
        {
          namespace = "kube-system"
        }
      ]
    }
  }

  # OIDC Provider
  enable_irsa = true

  tags = {
    Environment = var.environment
  }
}

# KMS key for EKS encryption
resource "aws_kms_key" "eks" {
  description             = "EKS Secret Encryption Key"
  deletion_window_in_days = 7
  enable_key_rotation     = true
}

# =============================================================================
# RDS PostgreSQL
# =============================================================================

module "rds" {
  source  = "terraform-aws-modules/rds/aws"
  version = "~> 6.0"

  identifier = "voting-db-${var.environment}"

  engine               = "postgres"
  engine_version       = "15.4"
  family               = "postgres15"
  major_engine_version = "15"
  instance_class       = "db.r6g.xlarge"

  allocated_storage     = 100
  max_allocated_storage = 500
  storage_encrypted     = true
  kms_key_id            = aws_kms_key.rds.arn

  db_name  = "voting_db"
  username = "voting_admin"
  port     = 5432

  multi_az               = true
  db_subnet_group_name   = module.vpc.database_subnet_group_name
  vpc_security_group_ids = [aws_security_group.rds.id]

  maintenance_window      = "Mon:00:00-Mon:03:00"
  backup_window           = "03:00-06:00"
  backup_retention_period = 30

  performance_insights_enabled          = true
  performance_insights_retention_period = 7
  create_monitoring_role                = true
  monitoring_interval                   = 60

  deletion_protection = true

  parameters = [
    {
      name  = "log_statement"
      value = "all"
    },
    {
      name  = "log_min_duration_statement"
      value = "1000"
    }
  ]
}

resource "aws_kms_key" "rds" {
  description             = "RDS Encryption Key"
  deletion_window_in_days = 7
  enable_key_rotation     = true
}

resource "aws_security_group" "rds" {
  name_prefix = "voting-rds-"
  vpc_id      = module.vpc.vpc_id

  ingress {
    from_port       = 5432
    to_port         = 5432
    protocol        = "tcp"
    security_groups = [module.eks.cluster_security_group_id]
  }
}

# =============================================================================
# ElastiCache Redis
# =============================================================================

resource "aws_elasticache_replication_group" "redis" {
  replication_group_id       = "voting-redis-${var.environment}"
  description                = "Redis cluster for voting system"
  node_type                  = "cache.r6g.large"
  num_cache_clusters         = 3
  port                       = 6379
  parameter_group_name       = "default.redis7"
  engine_version             = "7.0"
  automatic_failover_enabled = true
  multi_az_enabled           = true

  at_rest_encryption_enabled = true
  transit_encryption_enabled = true
  kms_key_id                 = aws_kms_key.redis.arn

  subnet_group_name  = aws_elasticache_subnet_group.redis.name
  security_group_ids = [aws_security_group.redis.id]

  snapshot_retention_limit = 7
  snapshot_window          = "05:00-09:00"
  maintenance_window       = "mon:09:00-mon:10:00"
}

resource "aws_elasticache_subnet_group" "redis" {
  name       = "voting-redis-subnet"
  subnet_ids = module.vpc.private_subnets
}

resource "aws_kms_key" "redis" {
  description             = "Redis Encryption Key"
  deletion_window_in_days = 7
  enable_key_rotation     = true
}

resource "aws_security_group" "redis" {
  name_prefix = "voting-redis-"
  vpc_id      = module.vpc.vpc_id

  ingress {
    from_port       = 6379
    to_port         = 6379
    protocol        = "tcp"
    security_groups = [module.eks.cluster_security_group_id]
  }
}

# =============================================================================
# CloudFront and WAF
# =============================================================================

resource "aws_cloudfront_distribution" "main" {
  enabled             = true
  is_ipv6_enabled     = true
  price_class         = "PriceClass_All"
  http_version        = "http2and3"
  web_acl_id          = aws_wafv2_web_acl.main.arn

  origin {
    domain_name = aws_lb.api.dns_name
    origin_id   = "api"

    custom_origin_config {
      http_port              = 80
      https_port             = 443
      origin_protocol_policy = "https-only"
      origin_ssl_protocols   = ["TLSv1.2"]
    }
  }

  default_cache_behavior {
    allowed_methods        = ["DELETE", "GET", "HEAD", "OPTIONS", "PATCH", "POST", "PUT"]
    cached_methods         = ["GET", "HEAD"]
    target_origin_id       = "api"
    viewer_protocol_policy = "redirect-to-https"
    compress               = true

    forwarded_values {
      query_string = true
      headers      = ["Authorization", "Origin", "Accept"]

      cookies {
        forward = "all"
      }
    }

    min_ttl     = 0
    default_ttl = 0
    max_ttl     = 0
  }

  restrictions {
    geo_restriction {
      restriction_type = "none"
    }
  }

  viewer_certificate {
    cloudfront_default_certificate = true
  }
}

# WAF Web ACL
resource "aws_wafv2_web_acl" "main" {
  name        = "voting-waf-${var.environment}"
  description = "WAF for Voting System"
  scope       = "CLOUDFRONT"

  default_action {
    allow {}
  }

  # AWS Managed Rules
  rule {
    name     = "AWSManagedRulesCommonRuleSet"
    priority = 1

    override_action {
      none {}
    }

    statement {
      managed_rule_group_statement {
        name        = "AWSManagedRulesCommonRuleSet"
        vendor_name = "AWS"
      }
    }

    visibility_config {
      cloudwatch_metrics_enabled = true
      metric_name                = "AWSManagedRulesCommonRuleSet"
      sampled_requests_enabled   = true
    }
  }

  rule {
    name     = "AWSManagedRulesKnownBadInputsRuleSet"
    priority = 2

    override_action {
      none {}
    }

    statement {
      managed_rule_group_statement {
        name        = "AWSManagedRulesKnownBadInputsRuleSet"
        vendor_name = "AWS"
      }
    }

    visibility_config {
      cloudwatch_metrics_enabled = true
      metric_name                = "AWSManagedRulesKnownBadInputsRuleSet"
      sampled_requests_enabled   = true
    }
  }

  # Rate limiting
  rule {
    name     = "RateLimitRule"
    priority = 3

    action {
      block {}
    }

    statement {
      rate_based_statement {
        limit              = 2000
        aggregate_key_type = "IP"
      }
    }

    visibility_config {
      cloudwatch_metrics_enabled = true
      metric_name                = "RateLimitRule"
      sampled_requests_enabled   = true
    }
  }

  visibility_config {
    cloudwatch_metrics_enabled = true
    metric_name                = "voting-waf"
    sampled_requests_enabled   = true
  }
}

# AWS Shield Advanced
resource "aws_shield_protection" "cloudfront" {
  name         = "voting-cloudfront-protection"
  resource_arn = aws_cloudfront_distribution.main.arn
}

# =============================================================================
# Application Load Balancer
# =============================================================================

resource "aws_lb" "api" {
  name               = "voting-api-${var.environment}"
  internal           = false
  load_balancer_type = "application"
  security_groups    = [aws_security_group.alb.id]
  subnets            = module.vpc.public_subnets

  enable_deletion_protection = true

  access_logs {
    bucket  = aws_s3_bucket.logs.id
    prefix  = "alb-logs"
    enabled = true
  }
}

resource "aws_security_group" "alb" {
  name_prefix = "voting-alb-"
  vpc_id      = module.vpc.vpc_id

  ingress {
    from_port   = 443
    to_port     = 443
    protocol    = "tcp"
    cidr_blocks = ["0.0.0.0/0"]
  }

  ingress {
    from_port   = 80
    to_port     = 80
    protocol    = "tcp"
    cidr_blocks = ["0.0.0.0/0"]
  }

  egress {
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
  }
}

# =============================================================================
# S3 Buckets
# =============================================================================

resource "aws_s3_bucket" "logs" {
  bucket = "voting-system-logs-${var.environment}-${data.aws_caller_identity.current.account_id}"
}

resource "aws_s3_bucket_versioning" "logs" {
  bucket = aws_s3_bucket.logs.id
  versioning_configuration {
    status = "Enabled"
  }
}

resource "aws_s3_bucket_server_side_encryption_configuration" "logs" {
  bucket = aws_s3_bucket.logs.id

  rule {
    apply_server_side_encryption_by_default {
      sse_algorithm     = "aws:kms"
      kms_master_key_id = aws_kms_key.s3.arn
    }
  }
}

resource "aws_kms_key" "s3" {
  description             = "S3 Encryption Key"
  deletion_window_in_days = 7
  enable_key_rotation     = true
}

data "aws_caller_identity" "current" {}

# =============================================================================
# SQS Queue for Vote Processing
# =============================================================================

resource "aws_sqs_queue" "vote_queue" {
  name                       = "voting-queue-${var.environment}"
  delay_seconds              = 0
  max_message_size           = 262144
  message_retention_seconds  = 86400
  receive_wait_time_seconds  = 10
  visibility_timeout_seconds = 60

  kms_master_key_id                 = aws_kms_key.sqs.arn
  kms_data_key_reuse_period_seconds = 300

  redrive_policy = jsonencode({
    deadLetterTargetArn = aws_sqs_queue.vote_dlq.arn
    maxReceiveCount     = 3
  })
}

resource "aws_sqs_queue" "vote_dlq" {
  name                      = "voting-dlq-${var.environment}"
  message_retention_seconds = 1209600 # 14 days
  kms_master_key_id         = aws_kms_key.sqs.arn
}

resource "aws_kms_key" "sqs" {
  description             = "SQS Encryption Key"
  deletion_window_in_days = 7
  enable_key_rotation     = true
}

# =============================================================================
# Outputs
# =============================================================================

output "vpc_id" {
  value = module.vpc.vpc_id
}

output "eks_cluster_endpoint" {
  value = module.eks.cluster_endpoint
}

output "eks_cluster_name" {
  value = module.eks.cluster_name
}

output "rds_endpoint" {
  value = module.rds.db_instance_endpoint
}

output "redis_endpoint" {
  value = aws_elasticache_replication_group.redis.primary_endpoint_address
}

output "cloudfront_domain" {
  value = aws_cloudfront_distribution.main.domain_name
}

output "sqs_queue_url" {
  value = aws_sqs_queue.vote_queue.url
}
