output "sns_topic_arn" {
  description = "SNS topic ARN — shared with all other modules for alerting"
  value       = aws_sns_topic.cost_alerts.arn
}
