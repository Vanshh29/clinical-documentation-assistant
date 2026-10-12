# ADR-006: Delivery and deployment design

- Status: Accepted
- Date: 2026-10-12

## Decisions
1. **One chart for the whole app.** `infra/helm/cda` deploys api, worker and web plus the jobs they need. A single version moves together, and per-environment differences live in `values-dev.yaml` and `values-prod.yaml`.
2. **Only the web pod is exposed.** The ingress routes everything to the web service; nginx forwards `/api` to the API inside the cluster. This is the same shape as the Compose stack, keeps the API off the public edge, and means metrics (port 9100) cannot be reached through the ingress.
3. **Migrations never race the rollout.** With a managed database (RDS) migrations run as a pre-upgrade hook (Helm) and PreSync hook (ArgoCD). With a database inside the release (local clusters) a hook would run before the database exists, so each API pod migrates in an init container instead. An advisory lock serializes concurrent migrators; a test fails without it.
4. **Hardened by default, enforced by tests.** Every pod runs as non-root with a read-only root filesystem, no capabilities, a default seccomp profile and no service-account token. Default-deny NetworkPolicies are opened per component. `infra/helm/tests` renders both environments and fails CI if any of this regresses.
5. **Secrets stay out of git.** Pods read one Kubernetes Secret. In AWS it is synced by External Secrets from Secrets Manager, whose value Terraform generates (database URL, encryption key, signing secret). The chart refuses to render a Secret unless `secrets.create` is set, which is for local clusters only.
6. **Kafka.** Dev runs a single-node Redpanda in the release. Prod expects a managed broker endpoint; none is provisioned here because a managed cluster would dominate the cost of a small deployment. The worker creates its topics with enough partitions at startup, and `maxReplicas` must not exceed the partition count.
7. **Images.** Immutable tags (`sha-<commit>`) in ECR with scan-on-push. CI scans before pushing and refuses `latest`. Charts refuse empty or `latest` tags.
8. **GitOps.** CI commits the new tag to `values-dev.yaml`; ArgoCD syncs dev automatically with self-heal. Prod changes arrive through a pull request opened by `promote-prod` and are applied by a manual sync after reviewing the diff.
9. **No stored cloud keys.** GitHub Actions assumes AWS roles through OIDC: one that can push images from `main`, and a read-only one for pull-request plans.
10. **Observability.** Prometheus metrics on a separate internal port (a ServiceMonitor is optional), JSON logs, optional OpenTelemetry traces. A worker heartbeat stops if its consumer, relay or reaper dies, so the liveness probe restarts a stuck pod.

## Known limits
- Authentication is a built-in token issuer for demos (ADR-002). A real deployment needs an identity provider before any real use.
- Traces are not propagated across Kafka messages.
- Database TLS uses `ssl=require` (encrypted, server not verified). `verify-full` needs the RDS CA bundle in the image.
- A single NAT gateway and single-node dev broker are cost choices, not availability choices.
