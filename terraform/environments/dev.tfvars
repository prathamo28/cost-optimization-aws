# =============================================================================
# Development environment — values
# =============================================================================

environment        = "dev"
aws_region         = "eu-west-1"
team               = "platform"
monthly_budget_usd = 500
alert_email        = "platform-team@example.com"

# Scheduling on — dev servers off outside business hours
enable_scheduling  = true
schedule_stop_cron = "cron(0 18 ? * MON-FRI *)"   # 18:00 UTC in dev
schedule_start_cron = "cron(0 7 ? * MON-FRI *)"

# Alert earlier in dev — catch runaway resources quickly
anomaly_threshold_percentage = 15

# S3 buckets to apply lifecycle policies
s3_bucket_ids = [
  "dev-app-assets",
  "dev-data-archive"
]

# SSM paths — secrets never stored in tfvars
anthropic_api_key_ssm_path = "/cost-optimization/dev/anthropic-api-key"
github_token_ssm_path      = "/cost-optimization/dev/github-token"
