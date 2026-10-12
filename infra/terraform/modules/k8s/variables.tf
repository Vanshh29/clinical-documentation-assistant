variable "cluster_name" {
  type = string
}

variable "kubernetes_version" {
  description = "EKS control plane version."
  type        = string
  default     = "1.30"
}

variable "private_subnet_ids" {
  type = list(string)
}

variable "public_subnet_ids" {
  type = list(string)
}

variable "endpoint_public_access" {
  description = "Expose the Kubernetes API on the internet, limited to api_allowed_cidrs. Off by default: reach a private endpoint through a VPN or bastion."
  type        = bool
  default     = false
}

variable "api_allowed_cidrs" {
  description = "Addresses allowed to reach the public Kubernetes API endpoint (only used when endpoint_public_access is true)."
  type        = list(string)
  default     = []
  validation {
    condition     = !contains(var.api_allowed_cidrs, "0.0.0.0/0")
    error_message = "0.0.0.0/0 would open the Kubernetes API to the whole internet. List specific addresses."
  }
}

variable "admin_principal_arns" {
  description = "IAM principals (users or roles) granted cluster-admin through EKS access entries."
  type        = list(string)
  default     = []
}

variable "node_instance_types" {
  type    = list(string)
  default = ["t3.medium"]
}

variable "node_capacity_type" {
  description = "ON_DEMAND or SPOT. Spot is cheaper but nodes can disappear: fine for dev."
  type        = string
  default     = "ON_DEMAND"
  validation {
    condition     = contains(["ON_DEMAND", "SPOT"], var.node_capacity_type)
    error_message = "node_capacity_type must be ON_DEMAND or SPOT."
  }
}

variable "node_disk_size_gb" {
  type    = number
  default = 30
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

variable "log_retention_days" {
  type    = number
  default = 30
}
