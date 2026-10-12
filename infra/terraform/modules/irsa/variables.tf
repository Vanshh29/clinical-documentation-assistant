variable "name" {
  type = string
}

variable "oidc_provider_arn" {
  type = string
}

variable "oidc_provider_url" {
  type = string
}

variable "namespace" {
  type = string
}

variable "service_account" {
  type = string
}

variable "managed_policy_arns" {
  type    = list(string)
  default = []
}

variable "inline_policy_json" {
  type    = string
  default = null
}
