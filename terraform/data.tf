# Current AWS account ID — used to scope IAM policies
data "aws_caller_identity" "current" {}

# Current AWS region
data "aws_region" "current" {}

# Fetch the Anthropic API key from SSM (stored securely, never in code)
data "aws_ssm_parameter" "anthropic_api_key" {
  name            = var.anthropic_api_key_ssm_path
  with_decryption = true
}

# Fetch the GitHub token from SSM
data "aws_ssm_parameter" "github_token" {
  name            = var.github_token_ssm_path
  with_decryption = true
}
