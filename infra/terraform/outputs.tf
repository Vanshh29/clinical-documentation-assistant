output "cluster_name" {
  value = module.k8s.cluster_name
}

output "cluster_endpoint" {
  value = module.k8s.cluster_endpoint
}

output "kubeconfig_command" {
  description = "Run this to point kubectl at the cluster."
  value       = "aws eks update-kubeconfig --region ${var.region} --name ${module.k8s.cluster_name}"
}

output "image_repositories" {
  description = "Put these in infra/helm/cda/values-<env>.yaml (images.*.repository)."
  value       = module.registry.repository_urls
}

output "database_endpoint" {
  value = module.db.endpoint
}

output "app_secret_arn" {
  description = "Secrets Manager secret synced into the cluster by External Secrets."
  value       = module.db.secret_arn
}

output "external_secrets_role_arn" {
  description = "Annotate the external-secrets service account with eks.amazonaws.com/role-arn."
  value       = module.external_secrets_irsa.role_arn
}

output "ci_push_role_arn" {
  description = "Set as the AWS_ROLE_ARN repository variable for the CD workflow."
  value       = aws_iam_role.ci_push.arn
}

output "ci_plan_role_arn" {
  description = "Set as the AWS_PLAN_ROLE_ARN repository variable for pull-request plans."
  value       = aws_iam_role.ci_plan.arn
}
