output "repository_urls" {
  description = "Repository URL per image."
  value       = { for k, r in aws_ecr_repository.this : k => r.repository_url }
}

output "repository_arns" {
  value = [for r in aws_ecr_repository.this : r.arn]
}
