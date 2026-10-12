resource "random_password" "db" {
  length  = 32
  special = false # keeps the connection URL free of characters that need escaping
}

resource "aws_db_subnet_group" "this" {
  name       = var.name
  subnet_ids = var.subnet_ids
}

resource "aws_security_group" "db" {
  name        = "${var.name}-db"
  description = "PostgreSQL from the Kubernetes nodes only"
  vpc_id      = var.vpc_id
}

resource "aws_vpc_security_group_ingress_rule" "from_nodes" {
  for_each                     = toset(var.allowed_security_group_ids)
  security_group_id            = aws_security_group.db.id
  referenced_security_group_id = each.value
  from_port                    = 5432
  to_port                      = 5432
  ip_protocol                  = "tcp"
  description                  = "PostgreSQL from application nodes"
}

resource "aws_db_parameter_group" "this" {
  name   = var.name
  family = "postgres16"

  parameter {
    name  = "rds.force_ssl"
    value = "1"
  }
  parameter {
    name  = "log_min_duration_statement"
    value = "1000"
  }
}

resource "aws_db_instance" "this" {
  identifier     = var.name
  engine         = "postgres"
  engine_version = var.engine_version
  instance_class = var.instance_class

  allocated_storage     = var.allocated_storage_gb
  max_allocated_storage = var.max_allocated_storage_gb
  storage_type          = "gp3"
  storage_encrypted     = true

  db_name  = var.database_name
  username = var.username
  password = random_password.db.result
  port     = 5432

  db_subnet_group_name   = aws_db_subnet_group.this.name
  vpc_security_group_ids = [aws_security_group.db.id]
  parameter_group_name   = aws_db_parameter_group.this.name
  publicly_accessible    = false
  multi_az               = var.multi_az

  backup_retention_period    = var.backup_retention_days
  copy_tags_to_snapshot      = true
  auto_minor_version_upgrade = true
  deletion_protection        = var.deletion_protection
  skip_final_snapshot        = var.skip_final_snapshot
  final_snapshot_identifier  = var.skip_final_snapshot ? null : "${var.name}-final"

  performance_insights_enabled    = false
  enabled_cloudwatch_logs_exports = ["postgresql"]
}

# Application secrets. The Fernet key must be 32 url-safe base64 bytes, padding included.
resource "random_id" "pii_key" {
  byte_length = 32
}

resource "random_password" "jwt" {
  length  = 48
  special = false
}

resource "aws_secretsmanager_secret" "app" {
  name                    = var.secret_name
  description             = "Application settings for ${var.name} (read by External Secrets)"
  recovery_window_in_days = var.secret_recovery_days
}

resource "aws_secretsmanager_secret_version" "app" {
  secret_id = aws_secretsmanager_secret.app.id
  secret_string = jsonencode({
    # ssl=require encrypts the connection. Use verify-full with the RDS CA bundle to also verify the server.
    database_url       = "postgresql+asyncpg://${var.username}:${random_password.db.result}@${aws_db_instance.this.address}:5432/${var.database_name}?ssl=require"
    pii_encryption_key = "${random_id.pii_key.b64_url}="
    auth_jwt_secret    = random_password.jwt.result
    openrouter_api_key = var.openrouter_api_key
  })
}
