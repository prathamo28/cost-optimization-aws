output "ebs_cleanup_lambda_arn" {
  value = module.storage_lifecycle_ebs.ebs_cleanup_lambda_arn
  description = "EBS cleanup Lambda ARN"
}

output "rightsizing_lambda_arn" {
  value = aws_lambda_function.rightsizing.arn
  description = "Rightsizing PR Lambda ARN"
}
