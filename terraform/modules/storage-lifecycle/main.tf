# =============================================================================
# Module: storage-lifecycle
# S3 tiering + expiry + EBS orphan cleanup Lambda
# =============================================================================

# ── S3 lifecycle policies ──────────────────────────────────────────────────

resource "aws_s3_bucket_lifecycle_configuration" "tiering" {
  for_each = toset(var.bucket_ids)
  bucket   = each.value

  rule {
    id     = "cost-tiering-and-expiry"
    status = "Enabled"

    transition {
      days          = 30
      storage_class = "STANDARD_IA"
    }
    transition {
      days          = 90
      storage_class = "GLACIER"
    }
    transition {
      days          = 180
      storage_class = "DEEP_ARCHIVE"
    }
    expiration {
      days = 365
    }
    # Clean up incomplete multipart uploads — small but real cost
    abort_incomplete_multipart_upload {
      days_after_initiation = 7
    }
  }
}

# Encryption enforced on all managed buckets
# checkov: CKV_AWS_19
resource "aws_s3_bucket_server_side_encryption_configuration" "enc" {
  for_each = toset(var.bucket_ids)
  bucket   = each.value

  rule {
    apply_server_side_encryption_by_default {
      sse_algorithm = "aws:kms"
    }
    bucket_key_enabled = true
  }
}

# Block all public access
# checkov: CKV_AWS_53/54/55/56
resource "aws_s3_bucket_public_access_block" "block" {
  for_each = toset(var.bucket_ids)
  bucket   = each.value

  block_public_acls       = true
  block_public_policy     = true
  ignore_public_acls      = true
  restrict_public_buckets = true
}

# ── EBS orphan cleanup Lambda ──────────────────────────────────────────────

resource "aws_iam_role" "ebs_cleanup" {
  name = "${var.name_prefix}-ebs-cleanup-role"
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

resource "aws_iam_role_policy" "ebs_cleanup" {
  name = "${var.name_prefix}-ebs-cleanup-policy"
  role = aws_iam_role.ebs_cleanup.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect = "Allow"
      Action = [
        "ec2:DescribeVolumes",
        "ec2:DescribeSnapshots",
        "ec2:DeleteSnapshot",
        "sns:Publish",
        "logs:CreateLogGroup",
        "logs:CreateLogStream",
        "logs:PutLogEvents"
      ]
      Resource = "*"
    }]
  })
}

resource "aws_lambda_function" "ebs_cleanup" {
  function_name = "${var.name_prefix}-ebs-cleanup"
  role          = aws_iam_role.ebs_cleanup.arn
  handler       = "ebs_cleanup.lambda_handler"
  runtime       = "python3.12"
  timeout       = 300
  filename      = "${path.module}/../../scripts/lambda/ebs_cleanup.zip"

  # checkov: CKV_AWS_50 — X-Ray tracing
  tracing_config { mode = "Active" }

  environment {
    variables = {
      ENVIRONMENT       = var.environment
      SNS_TOPIC_ARN     = var.sns_topic_arn
      SNAPSHOT_AGE_DAYS = "90"
    }
  }

  # checkov: CKV_AWS_116 — dead letter queue
  dead_letter_config {
    target_arn = var.sns_topic_arn
  }

  tags = var.tags
}

# Run every Sunday at 02:00 UTC
resource "aws_cloudwatch_event_rule" "ebs_cleanup" {
  name                = "${var.name_prefix}-ebs-cleanup-weekly"
  schedule_expression = "cron(0 2 ? * SUN *)"
  tags                = var.tags
}

resource "aws_cloudwatch_event_target" "ebs_cleanup" {
  rule = aws_cloudwatch_event_rule.ebs_cleanup.name
  arn  = aws_lambda_function.ebs_cleanup.arn
}

resource "aws_lambda_permission" "ebs_cleanup" {
  statement_id  = "AllowEventBridge"
  action        = "lambda:InvokeFunction"
  function_name = aws_lambda_function.ebs_cleanup.function_name
  principal     = "events.amazonaws.com"
  source_arn    = aws_cloudwatch_event_rule.ebs_cleanup.arn
}
