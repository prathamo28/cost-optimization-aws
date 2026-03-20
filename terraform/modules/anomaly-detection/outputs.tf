output "monitor_arn" {
  description = "Cost anomaly monitor ARN"
  value       = aws_ce_anomaly_monitor.service.arn
}

output "subscription_arn" {
  description = "Cost anomaly subscription ARN"
  value       = aws_ce_anomaly_subscription.alerts.arn
}
