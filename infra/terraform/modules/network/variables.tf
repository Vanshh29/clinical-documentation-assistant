variable "name" {
  description = "Name prefix for network resources."
  type        = string
}

variable "vpc_cidr" {
  description = "CIDR block of the VPC."
  type        = string
  default     = "10.0.0.0/16"
}

variable "az_count" {
  description = "Number of availability zones to span (EKS needs at least two)."
  type        = number
  default     = 2
  validation {
    condition     = var.az_count >= 2 && var.az_count <= 3
    error_message = "az_count must be 2 or 3."
  }
}

variable "single_nat_gateway" {
  description = "Share one NAT gateway across zones (cheaper, but a zone outage cuts egress)."
  type        = bool
  default     = true
}

variable "flow_log_retention_days" {
  description = "Retention of rejected-traffic flow logs."
  type        = number
  default     = 14
}
