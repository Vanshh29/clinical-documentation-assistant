#!/usr/bin/env bash
# Fill in the repository and image-registry placeholders used by the GitOps manifests.
#   scripts/configure-deploy.sh <github-owner>/<repo> <registry-host>
#   scripts/configure-deploy.sh acme/clinical-docs 123456789012.dkr.ecr.eu-central-1.amazonaws.com
# Set ROOT to operate on another checkout (used by the tests). Safe to run again.
set -euo pipefail

repo="${1:?usage: configure-deploy.sh <owner>/<repo> <registry-host>}"
registry="${2:?usage: configure-deploy.sh <owner>/<repo> <registry-host>}"
ROOT="${ROOT:-$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)}"

[[ "$repo" =~ ^[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+$ ]] || { echo "repo must look like owner/name" >&2; exit 2; }
[[ "$registry" =~ ^[A-Za-z0-9.-]+(:[0-9]+)?$ ]] || { echo "registry must be a host name, e.g. 123456789012.dkr.ecr.eu-central-1.amazonaws.com" >&2; exit 2; }

url="https://github.com/${repo}.git"
files=$(grep -rlE "OWNER/clinical-documentation-assistant|https://github.com/[^/]+/[^/]+\.git|REGISTRY/cda-|${registry//./\\.}/cda-" \
  "$ROOT/infra/argocd" "$ROOT/infra/helm/cda" --include='*.yaml' || true)

for f in $files; do
  # In-place edit that works with both GNU and BSD sed.
  sed -E -i.bak \
    -e "s#https://github.com/[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+\.git#${url}#g" \
    -e "s#(repository: )[^ ,}]*/(cda-(api|worker|web))#\1${registry}/\2#g" \
    "$f"
  rm -f "$f.bak"
done
echo "Updated: repository -> ${url}; registry -> ${registry}"
echo "Next: terraform output image_repositories should match; commit the change."
