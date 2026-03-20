output "scheduler_role_arn" {
  value = var.enabled ? aws_iam_role.scheduler[0].arn : null
}
