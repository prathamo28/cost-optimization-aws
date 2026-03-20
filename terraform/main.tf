# =============================================================================
# Cost Optimization — Root Module
# Calls all child modules and wires them together
# =============================================================================

module "scheduling" {
  source = "./modules/scheduling"

  enabled     = local.scheduling_enabled
  environment = var.environment
  team        = var.team
  name_prefix = local.name_prefix
  tags        = local.mandatory_tags

  stop_cron  = var.schedule_stop_cron
  start_cron = var.schedule_start_cron
}

module "storage_lifecycle" {
  source = "./modules/storage-lifecycle"

  bucket_ids  = var.s3_bucket_ids
  environment = var.environment
  name_prefix = local.name_prefix
  tags        = local.mandatory_tags

  sns_topic_arn = module.budgets.sns_topic_arn
}

module "budgets" {
  source = "./modules/budgets"

  team               = var.team
  environment        = var.environment
  name_prefix        = local.name_prefix
  monthly_budget_usd = var.monthly_budget_usd
  alert_email        = var.alert_email
  tags               = local.mandatory_tags
}

module "governance" {
  source = "./modules/governance"

  environment = var.environment
  name_prefix = local.name_prefix
  tags        = local.mandatory_tags

  sns_topic_arn      = module.budgets.sns_topic_arn
  anthropic_api_key  = data.aws_ssm_parameter.anthropic_api_key.value
  github_token       = data.aws_ssm_parameter.github_token.value
  account_id         = data.aws_caller_identity.current.account_id
}

module "anomaly_detection" {
  source = "./modules/anomaly-detection"

  team                         = var.team
  name_prefix                  = local.name_prefix
  tags                         = local.mandatory_tags
  sns_topic_arn                = module.budgets.sns_topic_arn
  anomaly_threshold_percentage = var.anomaly_threshold_percentage
}
