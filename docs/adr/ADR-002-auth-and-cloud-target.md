# ADR-002: Auth approach and cloud target

- Status: Accepted
- Date: 2026-10-12

## Decisions
1. **Auth:** OIDC-style JWT (HS256 in local dev, RS256/JWKS-ready interface) issued by a small mock token endpoint inside the API for local and demo use. Roles: `clinician`, `admin`. The API validates `iss`, `aud`, `exp` and a `role` claim through a `TokenVerifier` port, so replacing the mock with Keycloak or another OIDC provider changes configuration and one adapter, not the domain.
   *Why not Keycloak in Compose now:* ~1 GB RAM and slow startup hurt `make up` and CI; the security-relevant behavior (token validation, role checks, ownership checks) is identical.
2. **Cloud target: AWS EKS** (Terraform modules: network, k8s, db via RDS PostgreSQL, registry via ECR). Cost-conscious defaults: single small managed node group, single-AZ RDS `db.t4g.micro` for dev, documented `terraform destroy`.
   *Why AWS:* largest market share for the target roles; mature EKS/ArgoCD/External Secrets tooling.

## Consequences
- Production must swap the mock issuer for a real IdP; documented in the README security section.
- Kafka in cloud: Amazon MSK or Redpanda in-cluster; decided in Phase 6.
