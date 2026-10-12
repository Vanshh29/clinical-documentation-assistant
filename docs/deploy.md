# Deploying

> Demo only. Not a medical device. Not for real patient data.

## What has and has not been run
| Item | Status |
|---|---|
| Full stack in Docker Compose (`make up`), browser tests against it | Run and passing |
| Images build, run as non-root with a read-only filesystem | Run |
| Helm chart installed on a local Kubernetes cluster (kind): all pods healthy, migrations, topic creation, demo users, an approved note end to end | Run, then the cluster was removed |
| Helm lint/render, Kubernetes + CRD schema validation, policy tests | Run and passing |
| Terraform `fmt`, `validate`, `tflint` | Run and passing |
| ArgoCD manifest validation, GitHub workflow lint | Run and passing |
| `terraform plan` / `apply` against AWS | **Not run** (no AWS account was used) |
| ArgoCD syncing a cluster, EKS add-on setup, External Secrets with Secrets Manager | **Not run** |
| The GitHub Actions pipelines on GitHub | **Not run** (no remote repository yet) |

Treat the AWS path as reviewed and validated, not proven. Expect to fix small things on the first real apply.

## 1. Run it locally
```bash
make up        # http://localhost:8080
make down V=1  # stop and delete data
```

## 2. Run it on a local Kubernetes cluster (kind)
Needs Docker, [kind](https://kind.sigs.k8s.io/), kubectl and Helm.
```bash
kind create cluster --name cda
for c in api worker web; do docker build -f apps/$c/Dockerfile -t cda-$c:dev . ; done
kind load docker-image cda-api:dev cda-worker:dev cda-web:dev --name cda

# Local-only values; the file is never committed.
cat > /tmp/kind-values.yaml <<YAML
imagePullPolicy: Never
images:
  api:    { repository: cda-api,    tag: dev }
  worker: { repository: cda-worker, tag: dev }
  web:    { repository: cda-web,    tag: dev }
ingress: { enabled: false }
devInfra: { postgres: { enabled: true }, redpanda: { enabled: true } }
secrets:
  create: true
  values:
    POSTGRES_PASSWORD: change-me
    DATABASE_URL: postgresql+asyncpg://cda:change-me@cda-cda-postgres:5432/cda
    PII_ENCRYPTION_KEY: "$(python3 -c 'from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())')"
    AUTH_JWT_SECRET: "$(python3 -c 'import secrets; print(secrets.token_urlsafe(40))')"
YAML

helm upgrade --install cda infra/helm/cda -n cda --create-namespace \
  -f infra/helm/cda/values-dev.yaml -f /tmp/kind-values.yaml --wait
kubectl -n cda port-forward svc/cda-cda-web 8080:80     # http://localhost:8080
kind delete cluster --name cda                          # when finished
```

## 3. AWS (EKS, RDS, ECR)
Costs money while it runs: an EKS control plane, NAT gateway, worker nodes and an RDS instance are billed hourly. Destroy it when you are done (section 7).

1. **Remote state (once).**
   ```bash
   cd infra/terraform/bootstrap && terraform init && terraform apply
   ```
   Note the `state_bucket` and `lock_table` outputs.
2. **Configure.** Copy `infra/terraform/environments/dev.backend.hcl.example` to `dev.backend.hcl` (git-ignored) and fill it in. In `dev.tfvars` set `github_repository`, `state_bucket`, `lock_table`, and restrict `api_allowed_cidrs` to your network.
3. **Create the infrastructure.**
   ```bash
   cd infra/terraform
   terraform init -backend-config=environments/dev.backend.hcl
   terraform plan  -var-file=environments/dev.tfvars
   terraform apply -var-file=environments/dev.tfvars
   $(terraform output -raw kubeconfig_command)
   ```
4. **Point the manifests at your repository and registry.**
   ```bash
   scripts/configure-deploy.sh <owner>/<repo> <account>.dkr.ecr.<region>.amazonaws.com
   ```
5. **Cluster add-ons** (once per cluster): ingress-nginx, cert-manager, [External Secrets Operator](https://external-secrets.io) (annotate its service account with `terraform output external_secrets_role_arn` and create a `ClusterSecretStore` named `aws-secrets-manager`), [ArgoCD](https://argo-cd.readthedocs.io), and optionally the Prometheus Operator.
6. **GitHub settings.** Repository variables: `AWS_REGION`, `AWS_ROLE_ARN` (= `ci_push_role_arn`), `AWS_PLAN_ROLE_ARN`, `ECR_REGISTRY`, `TF_STATE_BUCKET`, `TF_LOCK_TABLE`. Protect `main` and require these checks: `secret-scan`, `api`, `worker`, `web`, `eval`, `helm`, `terraform`, `dependency-audit`, `images (api)`, `images (worker)`, `images (web)`, `config-scan`, `e2e`, `workflows`.
7. **Start GitOps.**
   ```bash
   kubectl apply -n argocd -f infra/argocd/project.yaml -f infra/argocd/root-app.yaml
   ```
   A push to `main` now builds and scans images, pushes `sha-<commit>` to ECR and commits the tag to `values-dev.yaml`; ArgoCD rolls dev out.
8. **Production.** Run the `promote-prod` workflow with a tag that has been running in dev. It opens a pull request; after merging, review the diff in ArgoCD and press Sync on `cda-prod`. Production needs its own `prod.tfvars` apply and a managed Kafka endpoint in `values-prod.yaml`.

## 4. Identity
The built-in token issuer exists for demos. Do not put real users behind it. Replace it with an OIDC provider by changing the token verifier (ADR-002); the demo-users job is already disabled in production values.

## 5. Operating it
- **Roll back:** revert the tag commit in `values-<env>.yaml`; ArgoCD (or a manual sync for prod) restores the previous images. Migrations are forward-only, so keep schema changes backwards compatible for one release.
- **Retention:** a daily CronJob deletes notes older than `config.retentionDays` (default 30) with their summaries and redaction maps, and records the count in the audit log.
- **Scaling:** HPAs scale api and web. The worker can scale up to the topic's partition count (`config.kafkaTopicPartitions`).
- **Metrics and traces:** `/metrics` on port 9100 of the api and worker pods (not exposed through the ingress); enable `monitoring.serviceMonitor`. Set `config.otlpEndpoint` for traces.
- **Logs:** JSON on stdout, never containing note text.

## 6. Checks that run on every pull request
Lint, types and tests for each app; the evaluation gate; Helm render, schema and policy checks; Terraform format, validate and tflint; dependency audits; image builds with vulnerability scans; misconfiguration scan; the browser tests against the built containers; workflow lint. Pull requests that touch Terraform also get a read-only `terraform plan`.

## 7. Tear down
```bash
kubectl delete -n argocd application cda-root         # removes dev and prod workloads
cd infra/terraform && terraform destroy -var-file=environments/dev.tfvars
cd bootstrap && terraform destroy                     # state bucket and lock table, last
```
Production sets `db_deletion_protection = true`; turn it off first if you really mean to delete.
