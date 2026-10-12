#!/usr/bin/env bash
# Run an infrastructure tool from a pinned container image, so nothing needs installing besides Docker.
#   scripts/tool.sh helm lint infra/helm/cda
#   scripts/tool.sh terraform -chdir=infra/terraform/envs/dev validate
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
tool="${1:?usage: tool.sh <helm|terraform|tflint|kubeconform|trivy|actionlint> [args...]}"
shift

case "$tool" in
  helm)        image="alpine/helm:3.16.2";                    entry=() ;;
  terraform)   image="hashicorp/terraform:1.9.8";             entry=() ;;
  tflint)      image="ghcr.io/terraform-linters/tflint:v0.53.0"; entry=() ;;
  kubeconform) image="ghcr.io/yannh/kubeconform:v0.6.7";      entry=() ;;
  trivy)       image="aquasec/trivy:0.57.0";                  entry=() ;;
  actionlint)  image="rhysd/actionlint:1.7.4";                entry=() ;;
  *) echo "unknown tool: $tool" >&2; exit 2 ;;
esac

exec docker run --rm -i \
  -v "$ROOT":/work -w /work \
  -e TF_IN_AUTOMATION=1 -e TF_PLUGIN_CACHE_DIR=/work/.tf-plugin-cache -e TFLINT_PLUGIN_DIR=/work/.tflint.d \
  "${entry[@]+"${entry[@]}"}" "$image" "$@"
