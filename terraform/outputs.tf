output "sns_topic_arn" {
  description = "SNS topic ARN for cost alerts — used by n8n webhook"
  value       = module.budgets.sns_topic_arn
}

output "anomaly_monitor_arn" {
  description = "Cost anomaly monitor ARN"
  value       = module.anomaly_detection.monitor_arn
}

output "ebs_cleanup_lambda_arn" {
  description = "ARN of the EBS cleanup Lambda function"
  value       = module.governance.ebs_cleanup_lambda_arn
}

output "rightsizing_lambda_arn" {
  description = "ARN of the rightsizing PR Lambda function"
  value       = module.governance.rightsizing_lambda_arn
}

output "scheduler_role_arn" {
  description = "IAM role ARN used by EventBridge Scheduler"
  value       = module.scheduling.scheduler_role_arn
}
