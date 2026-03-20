variable "bucket_ids"    { type = list(string) }
variable "environment"   { type = string }
variable "name_prefix"   { type = string }
variable "sns_topic_arn" { type = string }
variable "tags"          { type = map(string) }
