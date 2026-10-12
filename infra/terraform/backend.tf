# Remote state. The bucket and lock table come from ./bootstrap; pass the rest at init time:
#   terraform init -backend-config=environments/dev.backend.hcl
terraform {
  backend "s3" {}
}
