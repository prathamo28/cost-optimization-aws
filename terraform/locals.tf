locals {
  # Mandatory tags applied to every resource via module calls
  mandatory_tags = {
    "cost:team"    = var.team
    "cost:env"     = var.environment
    "cost:managed" = "terraform"
  }

  # Scheduling is only meaningful in non-prod environments
  scheduling_enabled = var.environment != "prod" && var.enable_scheduling

  # Resource name prefix keeps all resources identifiable by team and env
  name_prefix = "${var.team}-${var.environment}"

  # Anomaly monitor name
  anomaly_monitor_name = "${local.name_prefix}-cost-anomaly-monitor"
}
