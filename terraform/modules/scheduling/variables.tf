variable "enabled"     { type = bool }
variable "environment" { type = string }
variable "team"        { type = string }
variable "name_prefix" { type = string }
variable "stop_cron"   { type = string }
variable "start_cron"  { type = string }
variable "tags"        { type = map(string) }
