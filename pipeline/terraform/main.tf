terraform {
  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.0"
    }
    archive = {
      source  = "hashicorp/archive"
      version = "~> 2.0"
    }
  }
}

provider "aws" {
  region = var.aws_region
}


data "aws_caller_identity" "current" {}

# S3

resource "aws_s3_bucket" "health_data" {
  bucket = var.bucket_name
}

resource "aws_s3_bucket_versioning" "health_data" {
  bucket = aws_s3_bucket.health_data.id
  versioning_configuration {
    status = "Enabled"
  }
}

resource "aws_s3_bucket_public_access_block" "health_data" {
  bucket                  = aws_s3_bucket.health_data.id
  block_public_acls       = true
  block_public_policy     = true
  ignore_public_acls      = true
  restrict_public_buckets = true
}

resource "aws_s3_bucket_cors_configuration" "health_data" {
  bucket = aws_s3_bucket.health_data.id
  cors_rule {
    allowed_headers = ["*"]
    allowed_methods = ["GET", "HEAD"]
    allowed_origins = ["*"]
    max_age_seconds = 3000
  }
}

data "aws_iam_policy_document" "health_data_cloudfront" {
  statement {
    principals {
      type        = "Service"
      identifiers = ["cloudfront.amazonaws.com"]
    }
    actions   = ["s3:GetObject"]
    resources = ["${aws_s3_bucket.health_data.arn}/*"]
    condition {
      test     = "StringEquals"
      variable = "AWS:SourceArn"
      values   = [aws_cloudfront_distribution.frontend.arn]
    }
  }
}

resource "aws_s3_bucket_policy" "health_data" {
  bucket     = aws_s3_bucket.health_data.id
  policy     = data.aws_iam_policy_document.health_data_cloudfront.json
  depends_on = [aws_s3_bucket_public_access_block.health_data]
}

# SSM

resource "aws_ssm_parameter" "telegram_bot_token" {
  name  = "/ctbus_health/telegram/bot_token"
  type  = "SecureString"
  value = var.telegram_bot_token
}

resource "aws_ssm_parameter" "telegram_webhook_secret" {
  name  = "/ctbus_health/telegram/webhook_secret"
  type  = "SecureString"
  value = var.telegram_webhook_secret
}

resource "aws_ssm_parameter" "usda_api_key" {
  name  = "/ctbus_health/usda/api_key"
  type  = "SecureString"
  value = var.usda_api_key
}

resource "aws_ssm_parameter" "tavily_api_key" {
  name  = "/ctbus_health/tavily/api_key"
  type  = "SecureString"
  value = var.tavily_api_key
}

# SQS

resource "aws_sqs_queue" "food_dlq" {
  name                      = "ctbus-food-pipeline-dlq"
  message_retention_seconds = 1209600 # 14 days
}

resource "aws_sqs_queue" "food_queue" {
  name                       = "ctbus-food-pipeline"
  visibility_timeout_seconds = 300 # must be >= processor Lambda timeout
  message_retention_seconds  = 86400
  redrive_policy = jsonencode({
    deadLetterTargetArn = aws_sqs_queue.food_dlq.arn
    maxReceiveCount     = 3
  })
}
