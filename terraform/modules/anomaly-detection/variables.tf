variable "team"                         { type = string }
variable "name_prefix"                  { type = string }
variable "sns_topic_arn"               { type = string }
variable "anomaly_threshold_percentage" { type = number }
variable "tags"                         { type = map(string) }
