"""Policy checks on the rendered chart. Run: pytest infra/helm/tests  (needs helm, or Docker via scripts/tool.sh)."""

import re
import shutil
import subprocess
from pathlib import Path

import pytest
import yaml

ROOT = Path(__file__).resolve().parents[3]
CHART = ROOT / "infra" / "helm" / "cda"
HELM = (
    [shutil.which("helm")]
    if shutil.which("helm")
    else [str(ROOT / "scripts" / "tool.sh"), "helm"]
)
# Credential-looking names. LLM_MAX_INPUT_TOKENS is a model budget, not a credential, so TOKEN must be a whole word.
SECRET_NAME = re.compile(r"(PASSWORD|SECRET|API_KEY|ENCRYPTION_KEY|(^|_)TOKEN$)")
# Dev-only single-node broker image that needs a writable root filesystem.
WRITABLE_ROOT_EXCEPTIONS = {"redpanda"}


def render(*args: str) -> list[dict]:
    out = subprocess.run(
        [*HELM, "template", "cda", str(CHART.relative_to(ROOT) if HELM[0].endswith("tool.sh") else CHART),
         "--namespace", "cda", *args],
        check=True, capture_output=True, text=True, cwd=ROOT,
    ).stdout  # fmt: skip
    return [d for d in yaml.safe_load_all(out) if d]


@pytest.fixture(scope="module", params=["dev", "prod"])
def docs(request: pytest.FixtureRequest) -> list[dict]:
    values = f"infra/helm/cda/values-{request.param}.yaml"
    return render("-f", values if HELM[0].endswith("tool.sh") else str(ROOT / values))


def pod_specs(docs: list[dict]):
    for d in docs:
        kind = d["kind"]
        if kind in ("Deployment", "StatefulSet"):
            yield d, d["spec"]["template"]["spec"]
        elif kind == "Job":
            yield d, d["spec"]["template"]["spec"]
        elif kind == "CronJob":
            yield d, d["spec"]["jobTemplate"]["spec"]["template"]["spec"]


def containers(docs: list[dict]):
    for d, spec in pod_specs(docs):
        for c in spec["containers"]:
            yield d, spec, c


def test_every_pod_runs_as_non_root_with_a_default_seccomp_profile(
    docs: list[dict],
) -> None:
    for d, spec in pod_specs(docs):
        sc = spec["securityContext"]
        assert sc["runAsNonRoot"] is True, d["metadata"]["name"]
        assert sc["seccompProfile"]["type"] == "RuntimeDefault", d["metadata"]["name"]
        assert spec["automountServiceAccountToken"] is False, d["metadata"]["name"]


def test_every_container_drops_privileges(docs: list[dict]) -> None:
    for d, _, c in containers(docs):
        sc = c["securityContext"]
        assert sc["allowPrivilegeEscalation"] is False, c["name"]
        assert sc["capabilities"]["drop"] == ["ALL"], c["name"]
        if c["name"] not in WRITABLE_ROOT_EXCEPTIONS:
            assert sc["readOnlyRootFilesystem"] is True, (
                f"{d['metadata']['name']}/{c['name']}"
            )


def test_every_container_has_requests_and_a_memory_limit(docs: list[dict]) -> None:
    for _, _, c in containers(docs):
        res = c["resources"]
        assert res["requests"]["cpu"] and res["requests"]["memory"], c["name"]
        assert res["limits"]["memory"], c["name"]


def test_images_are_pinned_never_latest_or_untagged(docs: list[dict]) -> None:
    for _, _, c in containers(docs):
        image = c["image"]
        assert ":" in image.rsplit("/", 1)[-1], f"{image} has no tag"
        assert not image.endswith(":latest"), image


def test_long_running_workloads_have_liveness_probes(docs: list[dict]) -> None:
    for d in docs:
        if d["kind"] == "Deployment":
            for c in d["spec"]["template"]["spec"]["containers"]:
                assert "livenessProbe" in c, d["metadata"]["name"]
    api = next(
        d
        for d in docs
        if d["kind"] == "Deployment" and d["metadata"]["name"].endswith("-api")
    )
    c = api["spec"]["template"]["spec"]["containers"][0]
    assert c["readinessProbe"]["httpGet"]["path"] == "/readyz"


def test_no_plaintext_secrets_in_env_or_configmaps(docs: list[dict]) -> None:
    for _, _, c in containers(docs):
        for e in c.get("env", []):
            if SECRET_NAME.search(e["name"]):
                assert "valueFrom" in e and "value" not in e, (
                    f"{c['name']}: {e['name']} must come from a Secret"
                )
    for d in docs:
        if d["kind"] == "ConfigMap":
            assert not [k for k in d["data"] if SECRET_NAME.search(k)], d["metadata"][
                "name"
            ]
        assert d["kind"] != "Secret", (
            "the chart must not render Secrets unless secrets.create is set"
        )


def test_metrics_port_is_not_reachable_through_the_ingress(docs: list[dict]) -> None:
    ingress = next(d for d in docs if d["kind"] == "Ingress")
    backends = [
        p["backend"]["service"]["name"]
        for r in ingress["spec"]["rules"]
        for p in r["http"]["paths"]
    ]
    assert backends and all(b.endswith("-web") for b in backends)


def test_network_policy_denies_by_default_and_scopes_each_component(
    docs: list[dict],
) -> None:
    policies = {d["metadata"]["name"]: d for d in docs if d["kind"] == "NetworkPolicy"}
    deny = next(p for n, p in policies.items() if n.endswith("-default-deny"))
    assert deny["spec"]["policyTypes"] == ["Ingress", "Egress"]
    assert "ingress" not in deny["spec"] and "egress" not in deny["spec"]
    assert {"web", "api", "worker", "jobs"} <= {n.rsplit("-", 1)[-1] for n in policies}


def test_availability_controls_exist_for_replicated_services(docs: list[dict]) -> None:
    kinds = {(d["kind"], d["metadata"]["name"].rsplit("-", 1)[-1]) for d in docs}
    assert ("PodDisruptionBudget", "api") in kinds or (
        "HorizontalPodAutoscaler",
        "api",
    ) in kinds
    assert ("PodDisruptionBudget", "web") in kinds or (
        "HorizontalPodAutoscaler",
        "web",
    ) in kinds


def test_migrations_run_before_the_rollout_as_a_hook(docs: list[dict]) -> None:
    job = next(
        d
        for d in docs
        if d["kind"] == "Job" and d["metadata"]["name"].endswith("-migrate")
    )
    ann = job["metadata"]["annotations"]
    assert (
        "pre-upgrade" in ann["helm.sh/hook"]
        and ann["argocd.argoproj.io/hook"] == "PreSync"
    )
    assert job["spec"]["template"]["spec"]["containers"][0]["command"] == [
        "alembic",
        "upgrade",
        "head",
    ]


def test_retention_job_is_scheduled_and_cannot_overlap(docs: list[dict]) -> None:
    cron = next(d for d in docs if d["kind"] == "CronJob")
    assert cron["spec"]["concurrencyPolicy"] == "Forbid" and cron["spec"]["schedule"]


def test_prod_uses_external_secrets_and_no_demo_users() -> None:
    prod = render(
        "-f",
        "infra/helm/cda/values-prod.yaml"
        if HELM[0].endswith("tool.sh")
        else str(CHART / "values-prod.yaml"),
    )
    kinds = [d["kind"] for d in prod]
    assert "ExternalSecret" in kinds and "ServiceMonitor" in kinds
    assert not any(d["kind"] == "Job" and "seed" in d["metadata"]["name"] for d in prod)
    assert not any(
        d["kind"] == "StatefulSet" for d in prod
    )  # no in-cluster databases in prod


def values(env: str) -> str:
    rel = f"infra/helm/cda/values-{env}.yaml"
    return rel if HELM[0].endswith("tool.sh") else str(ROOT / rel)


def test_dev_uses_rds_plus_in_cluster_redpanda_and_demo_users() -> None:
    dev = render("-f", values("dev"))
    sets = {
        d["metadata"]["name"].rsplit("-", 1)[-1]
        for d in dev
        if d["kind"] == "StatefulSet"
    }
    assert sets == {"redpanda"}  # the database is the Terraform-managed RDS instance
    assert any(d["kind"] == "Job" and "seed" in d["metadata"]["name"] for d in dev)
    # RDS exists before the release, so migrations can safely be a pre-sync hook.
    assert any(
        d["kind"] == "Job" and d["metadata"]["name"].endswith("-migrate") for d in dev
    )


def init_names(docs: list[dict]) -> list[str]:
    api = next(
        d
        for d in docs
        if d["kind"] == "Deployment" and d["metadata"]["name"].endswith("-api")
    )
    return [
        c["name"] for c in api["spec"]["template"]["spec"].get("initContainers", [])
    ]


def test_in_cluster_postgres_migrates_in_an_init_container_not_a_hook() -> None:
    """Regression: a pre-install hook runs before the in-release database exists and would never succeed."""
    docs = render("-f", values("dev"), "--set", "devInfra.postgres.enabled=true")
    assert {
        d["metadata"]["name"].rsplit("-", 1)[-1]
        for d in docs
        if d["kind"] == "StatefulSet"
    } == {"postgres", "redpanda"}
    assert not any(
        d["kind"] == "Job" and d["metadata"]["name"].endswith("-migrate") for d in docs
    )
    assert init_names(docs) == ["migrate"]
    api = next(
        d
        for d in docs
        if d["kind"] == "Deployment" and d["metadata"]["name"].endswith("-api")
    )
    init = api["spec"]["template"]["spec"]["initContainers"][0]
    assert init["securityContext"]["readOnlyRootFilesystem"] is True
    assert "alembic upgrade head" in init["command"][-1]


def test_init_container_mode_can_be_chosen_explicitly() -> None:
    docs = render("-f", values("prod"), "--set", "migrations.mode=initContainer")
    assert init_names(docs) == ["migrate"]
    assert not any(
        d["kind"] == "Job" and d["metadata"]["name"].endswith("-migrate") for d in docs
    )


def test_migrations_can_be_disabled() -> None:
    docs = render("-f", values("prod"), "--set", "migrations.enabled=false")
    assert init_names(docs) == []
    assert not any(
        d["kind"] == "Job" and d["metadata"]["name"].endswith("-migrate") for d in docs
    )


def test_database_and_broker_policies_follow_the_in_cluster_services() -> None:
    docs = render("-f", values("dev"), "--set", "devInfra.postgres.enabled=true")
    names = {
        d["metadata"]["name"].rsplit("-", 1)[-1]
        for d in docs
        if d["kind"] == "NetworkPolicy"
    }
    assert "devinfra" in names
    worker = next(
        d
        for d in docs
        if d["kind"] == "NetworkPolicy" and d["metadata"]["name"].endswith("-worker")
    )
    peers = [str(rule["to"]) for rule in worker["spec"]["egress"]]
    assert any("postgres" in p for p in peers) and any("redpanda" in p for p in peers)


def test_latest_and_empty_image_tags_are_refused() -> None:
    for tag in ("latest", ""):
        r = subprocess.run(
            [*HELM, "template", "cda", "infra/helm/cda" if HELM[0].endswith("tool.sh") else str(CHART),
             "-f", "infra/helm/cda/values-dev.yaml" if HELM[0].endswith("tool.sh") else str(CHART / "values-dev.yaml"),
             "--set", f"images.api.tag={tag}"],
            capture_output=True, text=True, cwd=ROOT,
        )  # fmt: skip
        assert r.returncode != 0 and "images.api.tag" in r.stderr, tag
