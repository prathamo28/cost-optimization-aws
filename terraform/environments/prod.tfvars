# =============================================================================
# Production environment — values
# =============================================================================

environment        = "prod"
aws_region         = "eu-west-1"
team               = "platform"
monthly_budget_usd = 15000
alert_email        = "platform-team@example.com"

# Scheduling OFF in production — never stop prod servers automatically
enable_scheduling = false

# Higher threshold in prod — some spend increase is expected with growth
anomaly_threshold_percentage = 25

s3_bucket_ids = [
  "prod-app-assets",
  "prod-data-archive",
  "prod-logs",
  "prod-backups"
]

anthropic_api_key_ssm_path = "/cost-optimization/prod/anthropic-api-key"
github_token_ssm_path      = "/cost-optimization/prod/github-token"
