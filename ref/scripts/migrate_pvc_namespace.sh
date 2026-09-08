#!/usr/bin/env bash

set -Eeuo pipefail

usage() {
  printf 'Usage: %s <pvc> <source-namespace> <destination-namespace> [--yes]\n' "$0" >&2
  printf '\nMoves a PVC to another namespace while retaining and reusing its PV.\n' >&2
}

die() {
  printf 'Error: %s\n' "$*" >&2
  exit 1
}

[[ $# -ge 3 && $# -le 4 ]] || { usage; exit 2; }

pvc_name=$1
source_namespace=$2
destination_namespace=$3
auto_confirm=${4:-}

[[ -z "$pvc_name" || -z "$source_namespace" || -z "$destination_namespace" ]] && die 'PVC and namespace arguments must not be empty.'
[[ "$source_namespace" != "$destination_namespace" ]] || die 'Source and destination namespaces must differ.'
[[ -z "$auto_confirm" || "$auto_confirm" == '--yes' ]] || { usage; exit 2; }

command -v kubectl >/dev/null 2>&1 || die 'kubectl is required.'
command -v jq >/dev/null 2>&1 || die 'jq is required.'

kubectl get namespace "$source_namespace" >/dev/null || die "Source namespace does not exist: $source_namespace"
kubectl get namespace "$destination_namespace" >/dev/null || die "Destination namespace does not exist: $destination_namespace"

source_pvc_json=$(kubectl -n "$source_namespace" get pvc "$pvc_name" -o json) || die "PVC does not exist: $source_namespace/$pvc_name"
pv_name=$(jq -r '.spec.volumeName // empty' <<<"$source_pvc_json")
[[ -n "$pv_name" ]] || die "PVC is not bound to a PV: $source_namespace/$pvc_name"

kubectl get pv "$pv_name" >/dev/null || die "Bound PV does not exist: $pv_name"
pv_claim_namespace=$(kubectl get pv "$pv_name" -o jsonpath='{.spec.claimRef.namespace}')
pv_claim_name=$(kubectl get pv "$pv_name" -o jsonpath='{.spec.claimRef.name}')
[[ "$pv_claim_namespace" == "$source_namespace" && "$pv_claim_name" == "$pvc_name" ]] \
  || die "PV $pv_name is not claimed by $source_namespace/$pvc_name."

if kubectl -n "$destination_namespace" get pvc "$pvc_name" >/dev/null 2>&1; then
  die "Destination PVC already exists: $destination_namespace/$pvc_name"
fi

reclaim_policy=$(kubectl get pv "$pv_name" -o jsonpath='{.spec.persistentVolumeReclaimPolicy}')
printf 'PVC: %s/%s\nPV: %s\nCurrent reclaim policy: %s\nDestination: %s/%s\n' \
  "$source_namespace" "$pvc_name" "$pv_name" "$reclaim_policy" "$destination_namespace" "$pvc_name"

if [[ "$auto_confirm" != '--yes' ]]; then
  read -r -p 'Delete the source PVC and rebind this PV in the destination namespace? [y/N] ' answer
  [[ "$answer" =~ ^[Yy][Ee][Ss]$ ]] || { printf 'Aborted.\n'; exit 0; }
fi

kubectl patch pv "$pv_name" -p '{"spec":{"persistentVolumeReclaimPolicy":"Retain"}}' >/dev/null
kubectl -n "$source_namespace" delete pvc "$pvc_name" --wait=true

for attempt in {1..30}; do
  pv_phase=$(kubectl get pv "$pv_name" -o jsonpath='{.status.phase}' 2>/dev/null || true)
  [[ "$pv_phase" == 'Released' ]] && break
  [[ "$attempt" -eq 30 ]] && die "PV $pv_name did not become Released after deleting the source PVC (phase: ${pv_phase:-unknown})."
  sleep 1
done

claim_ref=$(kubectl get pv "$pv_name" -o json | jq -r 'if .spec.claimRef then "present" else "absent" end')
if [[ "$claim_ref" == 'present' ]]; then
  kubectl patch pv "$pv_name" --type=json -p='[{"op":"remove","path":"/spec/claimRef"}]' >/dev/null
fi

destination_pvc=$(mktemp)
trap 'rm -f "$destination_pvc"' EXIT
jq --arg name "$pvc_name" --arg namespace "$destination_namespace" --arg volume "$pv_name" '
  {
    apiVersion: "v1",
    kind: "PersistentVolumeClaim",
    metadata: ({name: $name, namespace: $namespace}
      + (if .metadata.labels then {labels: .metadata.labels} else {} end)
      + (if .metadata.annotations then {annotations: .metadata.annotations} else {} end)),
    spec: (.spec | del(.volumeName, .dataSource, .dataSourceRef) | .volumeName = $volume)
  }
' <<<"$source_pvc_json" >"$destination_pvc"

kubectl apply -f "$destination_pvc"
kubectl -n "$destination_namespace" wait --for=jsonpath='{.spec.volumeName}'="$pv_name" pvc/"$pvc_name" --timeout=60s

printf 'PVC migrated successfully: %s/%s -> %s/%s using PV %s\n' \
  "$source_namespace" "$pvc_name" "$destination_namespace" "$pvc_name" "$pv_name"