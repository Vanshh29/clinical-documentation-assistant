variable "name" {
  type = string
}

variable "vpc_id" {
  type = string
}

variable "subnet_ids" {
  description = "Private subnets for the database."
  type        = list(string)
}

variable "allowed_security_group_ids" {
  description = "Security groups allowed to connect (the Kubernetes nodes)."
  type        = list(string)
}

variable "engine_version" {
  type    = string
  default = "16.4"
}

variable "instance_class" {
  type    = string
  default = "db.t4g.micro"
}

variable "allocated_storage_gb" {
  type    = number
  default = 20
}

variable "max_allocated_storage_gb" {
  description = "Storage autoscaling ceiling."
  type        = number
  default     = 100
}

variable "database_name" {
  type    = string
  default = "cda"
}

variable "username" {
  type    = string
  default = "cda"
}

variable "multi_az" {
  type    = bool
  default = false
}

variable "backup_retention_days" {
  type    = number
  default = 7
}

variable "deletion_protection" {
  type    = bool
  default = false
}

variable "skip_final_snapshot" {
  type    = bool
  default = true
}

variable "secret_name" {
  description = "Secrets Manager name for the application secret."
  type        = string
  default     = "cda/app"
}

variable "secret_recovery_days" {
  description = "0 deletes immediately (dev). Use 7-30 in production."
  type        = number
  default     = 0
}

variable "openrouter_api_key" {
  description = "Optional model API key; leave empty to run on the offline provider."
  type        = string
  default     = ""
  sensitive   = true
}
