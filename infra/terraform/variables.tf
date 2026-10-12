variable "environment" {
  description = "dev or prod."
  type        = string
  validation {
    condition     = contains(["dev", "prod"], var.environment)
    error_message = "environment must be dev or prod."
  }
}

variable "region" {
  type    = string
  default = "eu-central-1"
}

variable "vpc_cidr" {
  type    = string
  default = "10.0.0.0/16"
}

variable "az_count" {
  type    = number
  default = 2
}

variable "single_nat_gateway" {
  description = "One shared NAT gateway (cheaper) instead of one per zone."
  type        = bool
  default     = true
}

variable "kubernetes_version" {
  type    = string
  default = "1.30"
}

variable "endpoint_public_access" {
  description = "Expose the Kubernetes API on the internet, limited to api_allowed_cidrs. Off by default."
  type        = bool
  default     = false
}

variable "api_allowed_cidrs" {
  description = "Addresses allowed to reach the public Kubernetes API (only used when endpoint_public_access is true). 0.0.0.0/0 is rejected."
  type        = list(string)
  default     = []
}

variable "admin_principal_arns" {
  description = "IAM users/roles that administer the cluster."
  type        = list(string)
  default     = []
}

variable "node_instance_types" {
  type    = list(string)
  default = ["t3.medium"]
}

variable "node_capacity_type" {
  type    = string
  default = "ON_DEMAND"
}

variable "node_desired_size" {
  type    = number
  default = 2
}

variable "node_min_size" {
  type    = number
  default = 2
}

variable "node_max_size" {
  type    = number
  default = 4
}

variable "db_instance_class" {
  type    = string
  default = "db.t4g.micro"
}

variable "db_multi_az" {
  type    = bool
  default = false
}

variable "db_backup_retention_days" {
  type    = number
  default = 7
}

variable "db_deletion_protection" {
  type    = bool
  default = false
}

variable "db_skip_final_snapshot" {
  type    = bool
  default = true
}

variable "secret_recovery_days" {
  type    = number
  default = 0
}

variable "openrouter_api_key" {
  description = "Optional. Leave empty to run on the offline provider."
  type        = string
  default     = ""
  sensitive   = true
}

variable "github_repository" {
  description = "owner/name of the repository allowed to assume the CI roles through GitHub OIDC."
  type        = string
}

variable "create_github_oidc_provider" {
  description = "Set to false if the account already has the GitHub OIDC provider."
  type        = bool
  default     = true
}

variable "state_bucket" {
  description = "Remote-state bucket (from ./bootstrap); lets the read-only plan role read state."
  type        = string
}

variable "lock_table" {
  description = "DynamoDB state-lock table (from ./bootstrap)."
  type        = string
}
