variable "name_prefix" {
  description = "Repository name prefix, e.g. cda gives cda-api."
  type        = string
  default     = "cda"
}

variable "repositories" {
  description = "Image repositories to create."
  type        = list(string)
  default     = ["api", "worker", "web"]
}

variable "keep_last" {
  description = "How many tagged images to retain per repository."
  type        = number
  default     = 20
}
