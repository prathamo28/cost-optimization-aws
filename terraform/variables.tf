variable "aws_region" {
  description = "AWS region to deploy resources into"
  type        = string
  default     = "eu-west-1"
}

variable "environment" {
  description = "Deployment environment"
  type        = string
  validation {
    condition     = contains(["dev", "staging", "prod"], var.environment)
    error_message = "Environment must be dev, staging, or prod."
  }
}

variable "team" {
  description = "Owning team name — used for cost allocation tags and resource naming"
  type        = string
}

variable "monthly_budget_usd" {
  description = "Monthly cost budget in USD for this team"
  type        = number
}

variable "alert_email" {
  description = "Email address for budget and anomaly alerts"
  type        = string
}

variable "s3_bucket_ids" {
  description = "List of S3 bucket IDs to apply lifecycle policies to"
  type        = list(string)
  default     = []
}

variable "enable_scheduling" {
  description = "Enable non-production start/stop scheduling. Always false in prod."
  type        = bool
  default     = true
}

variable "schedule_stop_cron" {
  description = "Cron expression for stopping non-prod resources (UTC)"
  type        = string
  default     = "cron(0 19 ? * MON-FRI *)"
}

variable "schedule_start_cron" {
  description = "Cron expression for starting non-prod resources (UTC)"
  type        = string
  default     = "cron(0 6 ? * MON-FRI *)"
}

variable "anomaly_threshold_percentage" {
  description = "Percentage above expected spend to trigger an anomaly alert"
  type        = number
  default     = 20
}

variable "slack_webhook_url" {
  description = "Slack webhook URL for cost alerts. Store in SSM, not here."
  type        = string
  sensitive   = true
  default     = ""
}

variable "github_token_ssm_path" {
  description = "SSM Parameter Store path for the GitHub token used by Lambda scripts"
  type        = string
  default     = "/cost-optimization/github-token"
}

variable "anthropic_api_key_ssm_path" {
  description = "SSM Parameter Store path for the Anthropic API key"
  type        = string
  default     = "/cost-optimization/anthropic-api-key"
}
