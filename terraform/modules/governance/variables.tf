variable "environment" { type = string }
variable "name_prefix" { type = string }
variable "sns_topic_arn" { type = string }
variable "anthropic_api_key" {
  type      = string
  sensitive = true
}

variable "github_token" {
  type      = string
  sensitive = true
}
variable "account_id" { type = string }
variable "tags" { type = map(string) }
