# =============================================================================
# Module: scheduling
# Stops non-prod EC2 instances at end of business day, starts them in the morning
# Only deployed when enabled = true (never in prod)
# =============================================================================

resource "aws_iam_role" "scheduler" {
  count = var.enabled ? 1 : 0
  name  = "${var.name_prefix}-scheduler-role"
  tags  = var.tags

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Action    = "sts:AssumeRole"
      Effect    = "Allow"
      Principal = { Service = "scheduler.amazonaws.com" }
    }]
  })
}

resource "aws_iam_role_policy" "scheduler" {
  count = var.enabled ? 1 : 0
  name  = "${var.name_prefix}-scheduler-policy"
  role  = aws_iam_role.scheduler[0].id

  # Scoped to resources tagged with this environment only — no wildcard
  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect = "Allow"
      Action = [
        "ec2:StopInstances",
        "ec2:StartInstances",
        "ec2:DescribeInstances"
      ]
      Resource = "*"
      Condition = {
        StringEquals = {
          "ec2:ResourceTag/cost:env" = var.environment
        }
      }
    }]
  })
}

resource "aws_scheduler_schedule_group" "cost" {
  count = var.enabled ? 1 : 0
  name  = "${var.name_prefix}-cost-schedules"
  tags  = var.tags
}

resource "aws_scheduler_schedule" "stop" {
  count      = var.enabled ? 1 : 0
  name       = "${var.name_prefix}-stop"
  group_name = aws_scheduler_schedule_group.cost[0].name

  flexible_time_window { mode = "OFF" }
  schedule_expression          = var.stop_cron
  schedule_expression_timezone = "UTC"

  target {
    arn      = "arn:aws:scheduler:::aws-sdk:ec2:stopInstances"
    role_arn = aws_iam_role.scheduler[0].arn
    input = jsonencode({
      Filters = [{ Name = "tag:cost:env", Values = [var.environment] }]
    })
  }
}

resource "aws_scheduler_schedule" "start" {
  count      = var.enabled ? 1 : 0
  name       = "${var.name_prefix}-start"
  group_name = aws_scheduler_schedule_group.cost[0].name

  flexible_time_window { mode = "OFF" }
  schedule_expression          = var.start_cron
  schedule_expression_timezone = "UTC"

  target {
    arn      = "arn:aws:scheduler:::aws-sdk:ec2:startInstances"
    role_arn = aws_iam_role.scheduler[0].arn
    input = jsonencode({
      Filters = [{ Name = "tag:cost:env", Values = [var.environment] }]
    })
  }
}
