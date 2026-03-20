package cost

import future.keywords.in

# =============================================================================
# OPA / Conftest cost and security policies
# Run against terraform plan JSON output:
#   terraform plan -out=plan.tfplan
#   terraform show -json plan.tfplan > plan.json
#   conftest test plan.json --policy ./policies/ --namespace cost
# =============================================================================

# ── RULE 1: Block oversized instances in non-prod ──────────────────────────

deny[msg] {
  resource := input.resource_changes[_]
  resource.type == "aws_instance"
  resource.change.after.instance_type in [
    "m5.2xlarge", "m5.4xlarge", "m5.8xlarge",
    "r5.2xlarge", "r5.4xlarge",
    "p3.2xlarge", "p4d.24xlarge",
    "x2idn.16xlarge"
  ]
  resource.change.after.tags["cost:env"] != "prod"
  msg := sprintf(
    "COST-001: Instance type %v is not allowed in non-prod. Use t3.medium or m5.large. Resource: %v",
    [resource.change.after.instance_type, resource.address]
  )
}

# ── RULE 2: Require mandatory cost tags on all resources ───────────────────

deny[msg] {
  resource := input.resource_changes[_]
  resource.change.actions != ["delete"]
  not resource.change.after.tags["cost:team"]
  msg := sprintf(
    "COST-002: Resource %v is missing required tag cost:team.",
    [resource.address]
  )
}

deny[msg] {
  resource := input.resource_changes[_]
  resource.change.actions != ["delete"]
  not resource.change.after.tags["cost:env"]
  msg := sprintf(
    "COST-003: Resource %v is missing required tag cost:env.",
    [resource.address]
  )
}

# ── RULE 3: Block Multi-AZ RDS in non-prod ────────────────────────────────

deny[msg] {
  resource := input.resource_changes[_]
  resource.type == "aws_db_instance"
  resource.change.after.multi_az == true
  resource.change.after.tags["cost:env"] != "prod"
  msg := sprintf(
    "COST-004: RDS Multi-AZ is not allowed in non-prod environment '%v'. Estimated waste: $200+/month. Resource: %v",
    [resource.change.after.tags["cost:env"], resource.address]
  )
}

# ── RULE 4: Warn on S3 buckets without lifecycle rules ─────────────────────

warn[msg] {
  resource := input.resource_changes[_]
  resource.type == "aws_s3_bucket"
  resource.change.actions != ["delete"]
  not resource.change.after.lifecycle_rule
  msg := sprintf(
    "COST-005: S3 bucket %v has no lifecycle rule. Objects will accumulate in Standard tier.",
    [resource.address]
  )
}

# ── RULE 5: Block unencrypted EBS volumes ─────────────────────────────────

deny[msg] {
  resource := input.resource_changes[_]
  resource.type == "aws_ebs_volume"
  resource.change.after.encrypted != true
  msg := sprintf(
    "SEC-001: EBS volume %v is not encrypted. Violates security baseline (CKV_AWS_3).",
    [resource.address]
  )
}

# ── RULE 6: Block Lambda without tracing ──────────────────────────────────

deny[msg] {
  resource := input.resource_changes[_]
  resource.type == "aws_lambda_function"
  resource.change.after.tracing_config[_].mode != "Active"
  msg := sprintf(
    "SEC-002: Lambda function %v does not have X-Ray tracing enabled (CKV_AWS_50).",
    [resource.address]
  )
}

# ── RULE 7: Block SNS topics without encryption ───────────────────────────

deny[msg] {
  resource := input.resource_changes[_]
  resource.type == "aws_sns_topic"
  not resource.change.after.kms_master_key_id
  msg := sprintf(
    "SEC-003: SNS topic %v is not encrypted with KMS.",
    [resource.address]
  )
}
