# =============================================================================
# Module: governance
# AWS Config tagging rules, Security Hub integration,
# rightsizing Lambda, and config auto-remediation
# =============================================================================

# ── AWS Config — required tags rule ────────────────────────────────────────

resource "aws_config_config_rule" "required_tags" {
  name = "${var.name_prefix}-required-tags"
  tags = var.tags

  source {
    owner             = "AWS"
    source_identifier = "REQUIRED_TAGS"
  }

  input_parameters = jsonencode({
    tag1Key = "cost:team"
    tag2Key = "cost:env"
    tag3Key = "cost:managed"
  })

  scope {
    compliance_resource_types = [
      "AWS::EC2::Instance",
      "AWS::RDS::DBInstance",
      "AWS::S3::Bucket",
      "AWS::ECS::Service",
      "AWS::Lambda::Function"
    ]
  }
}

# ── Security Hub — enable and subscribe Config findings ────────────────────

resource "aws_securityhub_account" "main" {}

resource "aws_securityhub_product_subscription" "config" {
  depends_on  = [aws_securityhub_account.main]
  product_arn = "arn:aws:securityhub:${data.aws_region.current.name}::product/aws/config"
}

data "aws_region" "current" {}

# ── Rightsizing Lambda ──────────────────────────────────────────────────────

resource "aws_iam_role" "rightsizing" {
  name = "${var.name_prefix}-rightsizing-role"
  tags = var.tags

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Action    = "sts:AssumeRole"
      Effect    = "Allow"
      Principal = { Service = "lambda.amazonaws.com" }
    }]
  })
}

resource "aws_iam_role_policy" "rightsizing" {
  name = "${var.name_prefix}-rightsizing-policy"
  role = aws_iam_role.rightsizing.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect = "Allow"
      Action = [
        "compute-optimizer:GetEC2InstanceRecommendations",
        "compute-optimizer:GetECSServiceRecommendations",
        "compute-optimizer:GetLambdaFunctionRecommendations",
        "ec2:DescribeInstances",
        "logs:CreateLogGroup",
        "logs:CreateLogStream",
        "logs:PutLogEvents",
        "ssm:GetParameter"
      ]
      Resource = "*"
    }]
  })
}

resource "aws_lambda_function" "rightsizing" {
  function_name = "${var.name_prefix}-rightsizing-pr"
  role          = aws_iam_role.rightsizing.arn
  handler       = "rightsizing_pr.lambda_handler"
  runtime       = "python3.12"
  timeout       = 300
  filename      = "${path.module}/../../scripts/lambda/rightsizing_pr.zip"

  tracing_config { mode = "Active" }

  environment {
    variables = {
      ENVIRONMENT         = var.environment
      GITHUB_TOKEN        = var.github_token
      ANTHROPIC_API_KEY   = var.anthropic_api_key
      SNS_TOPIC_ARN       = var.sns_topic_arn
    }
  }

  dead_letter_config {
    target_arn = var.sns_topic_arn
  }

  tags = var.tags
}

# Run every Monday at 07:00 UTC — before engineers start work
resource "aws_cloudwatch_event_rule" "rightsizing_weekly" {
  name                = "${var.name_prefix}-rightsizing-weekly"
  schedule_expression = "cron(0 7 ? * MON *)"
  tags                = var.tags
}

resource "aws_cloudwatch_event_target" "rightsizing" {
  rule = aws_cloudwatch_event_rule.rightsizing_weekly.name
  arn  = aws_lambda_function.rightsizing.arn
}

resource "aws_lambda_permission" "rightsizing" {
  statement_id  = "AllowEventBridge"
  action        = "lambda:InvokeFunction"
  function_name = aws_lambda_function.rightsizing.function_name
  principal     = "events.amazonaws.com"
  source_arn    = aws_cloudwatch_event_rule.rightsizing_weekly.arn
}
