output "endpoint" {
  value = aws_db_instance.this.address
}

output "security_group_id" {
  value = aws_security_group.db.id
}

output "secret_arn" {
  description = "Secrets Manager secret the cluster reads through External Secrets."
  value       = aws_secretsmanager_secret.app.arn
}
