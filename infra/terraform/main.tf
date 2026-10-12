provider "aws" {
  region = var.region

  default_tags {
    tags = {
      Project     = "clinical-documentation-assistant"
      Environment = var.environment
      ManagedBy   = "terraform"
    }
  }
}

locals {
  name = "cda-${var.environment}"
}

module "network" {
  source             = "./modules/network"
  name               = local.name
  vpc_cidr           = var.vpc_cidr
  az_count           = var.az_count
  single_nat_gateway = var.single_nat_gateway
}

module "k8s" {
  source               = "./modules/k8s"
  cluster_name         = local.name
  kubernetes_version   = var.kubernetes_version
  private_subnet_ids   = module.network.private_subnet_ids
  public_subnet_ids    = module.network.public_subnet_ids
  api_allowed_cidrs    = var.api_allowed_cidrs
  admin_principal_arns = var.admin_principal_arns
  node_instance_types  = var.node_instance_types
  node_capacity_type   = var.node_capacity_type
  node_desired_size    = var.node_desired_size
  node_min_size        = var.node_min_size
  node_max_size        = var.node_max_size
}

module "db" {
  source                     = "./modules/db"
  name                       = local.name
  vpc_id                     = module.network.vpc_id
  subnet_ids                 = module.network.private_subnet_ids
  allowed_security_group_ids = [module.k8s.cluster_security_group_id]
  instance_class             = var.db_instance_class
  multi_az                   = var.db_multi_az
  backup_retention_days      = var.db_backup_retention_days
  deletion_protection        = var.db_deletion_protection
  skip_final_snapshot        = var.db_skip_final_snapshot
  secret_name                = "cda/${var.environment}/app"
  secret_recovery_days       = var.secret_recovery_days
  openrouter_api_key         = var.openrouter_api_key
}

module "registry" {
  source      = "./modules/registry"
  name_prefix = "cda"
}

# External Secrets Operator reads only the application secret.
data "aws_iam_policy_document" "external_secrets" {
  statement {
    actions   = ["secretsmanager:GetSecretValue", "secretsmanager:DescribeSecret"]
    resources = [module.db.secret_arn]
  }
}

module "external_secrets_irsa" {
  source             = "./modules/irsa"
  name               = "${local.name}-external-secrets"
  oidc_provider_arn  = module.k8s.oidc_provider_arn
  oidc_provider_url  = module.k8s.oidc_provider_url
  namespace          = "external-secrets"
  service_account    = "external-secrets"
  inline_policy_json = data.aws_iam_policy_document.external_secrets.json
}
