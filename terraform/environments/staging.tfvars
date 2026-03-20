# =============================================================================
# Staging environment — values
# =============================================================================

environment        = "staging"
aws_region         = "eu-west-1"
team               = "platform"
monthly_budget_usd = 2000
alert_email        = "platform-team@example.com"

# Scheduling on — staging off outside business hours
enable_scheduling   = true
schedule_stop_cron  = "cron(0 19 ? * MON-FRI *)"   # 19:00 UTC
schedule_start_cron = "cron(0 6 ? * MON-FRI *)"    # 06:00 UTC

anomaly_threshold_percentage = 20

s3_bucket_ids = [
  "staging-app-assets",
  "staging-data-archive",
  "staging-logs"
]

anthropic_api_key_ssm_path = "/cost-optimization/staging/anthropic-api-key"
github_token_ssm_path      = "/cost-optimization/staging/github-token"
