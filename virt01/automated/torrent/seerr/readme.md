# Seerr Umbrella Chart

This repository contains the Helm umbrella chart for deploying **Seerr** via ArgoCD. It uses an OCI-based dependency and a custom alias to simplify configuration.

## Prerequisites

- **Helm 3.8.0+** (Required for OCI registry support)
- **Kubectl** (For manual verification)
- **ArgoCD** (For automated deployment)

---

Homepage:
  <https://docs.seerr.dev/>


## 1. Fetching the Chart
Because the Seerr chart is hosted on GitHub Container Registry (OCI), you must pull the dependency into your local `charts/` folder before you can template or test it.

```bash
helm repo add seerr oci://ghcr.io/seerr-team/seerr/seerr-chart
# Update and download the seerr-chart dependency
helm dependency update
```

## 2. Updating the Chart

To update the version of Seerr you are deploying:

1. Open `Chart.yaml`.
2. Change the version under the `dependencies` section (for example, from `3.3.0` to `3.4.0`).
3. Refresh the lock file:

```bash
rm Chart.lock
helm dependency update
```

4. Commit the updated `Chart.yaml` and `Chart.lock` to your Git repository for ArgoCD to pick up.

## 3. Testing Your Values

Before syncing to ArgoCD, verify that your `values.yaml` (using the `seerr` alias) correctly overrides the subchart defaults.

### Preview Rendered Manifests

Use the template command to see the final Kubernetes YAML that will be sent to the cluster:

```bash
helm template my-release . -f values.yaml
```

### View Merged Computed Values

To see exactly how Helm has merged your overrides with the subchart defaults:

```bash
helm install my-test-release . -f values.yaml --dry-run --debug
```

## 4. Dual Ingress Configuration

This chart is configured to support two separate Ingress resources to handle different cert-manager `ClusterIssuer` values (internal vs. external).

- Internal URL: Uses `nf-lab` issuer for `.k3s.nf.lab` domains.
- External URL: Uses `letsencrypt-production` (or your chosen provider) for `seerr.nforcer.com`.

Important: Ensure `seerr.ingress.enabled` is set to `false` in your `values.yaml` if you are using custom Ingress templates in the `templates/` directory to avoid resource conflicts.
