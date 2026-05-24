variable "aws_region" {
  type    = string
  default = "us-east-1"
}

variable "bucket_name" {
  type    = string
  default = "ctbus-health-data"
}

variable "telegram_bot_token" {
  type      = string
  sensitive = true
}

variable "telegram_webhook_secret" {
  type        = string
  sensitive   = true
  description = "Random string Telegram echoes on every webhook request for validation (A-Z, a-z, 0-9, _, - only)"
}

variable "usda_api_key" {
  type      = string
  sensitive = true
}

variable "bedrock_model_id" {
  type        = string
  default     = "us.anthropic.claude-haiku-4-5-20251001-v1:0"
  description = "Bedrock model ID (cross-region inference profile) used by the processor"
}

variable "tavily_api_key" {
  type      = string
  sensitive = true
  description = "Tavily search API key for restaurant menu lookup"
}

variable "google_client_id" {
  type      = string
  sensitive = true
  description = "Google OAuth 2.0 client ID for Cognito federation"
}

variable "google_client_secret" {
  type      = string
  sensitive = true
  description = "Google OAuth 2.0 client secret for Cognito federation"
}

variable "domain_name" {
  type        = string
  default     = "food.charliebushman.com"
  description = "Custom domain for the frontend"
}

variable "allowed_emails" {
  type        = list(string)
  description = "Email addresses permitted to sign up via Cognito"
}
