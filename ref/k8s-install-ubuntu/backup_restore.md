# Velero CLI Installation and Restore Guide

This guide provides instructions on how to install Velero CLI client v1.18.2 and perform a backup restore in a Kubernetes cluster.

## Installation (Linux AMD64)

### Prerequisites
* A running Kubernetes cluster.
* `kubectl` installed and configured to access your cluster.

### 1. Download and Extract the Binary
Download the specific v1.18.2 Linux binary directly from the official Velero repository releases:

```bash
# Download the archive
curl -L https://github.com/vmware-tanzu/velero/releases/download/v1.18.2/velero-v1.18.2-linux-amd64.tar.gz -o /tmp/velero-v1.18.2-linux-amd64.tar.gz
tar -xvf /tmp/velero-v1.18.2-linux-amd64.tar.gz -C /tmp/
sudo install -m 0755 /tmp/velero-v1.18.2-linux-amd64/velero /usr/local/bin/velero
rm -rf /tmp/velero-v1.18.2-linux-amd64.tar.gz /tmp/velero-v1.18.2-linux-amd64/
```

### 4. Verify Installation
Ensure that the client version matches and can execute successfully:

```bash
velero version --client-only
```

---

## How to Restore a Backup

### 1. Find Your Target Backup
Query the active backups inside the cluster environment and filter specifically for the application stack (e.g., `smallstep`):

```bash
velero get backups | grep smallstep
```

**Example Output:**
```text
smallstep-smallstep-20260712090027           Completed          0        0          2026-07-12 05:00:27 -0400 EDT   9d        default            app.kubernetes.io/instance=smallstep
smallstep-smallstep-20260705090015           Completed          0        0          2026-07-05 05:00:15 -0400 EDT   2d        default            app.kubernetes.io/instance=smallstep
```

### 2. Prepare ArgoCD (Scale Down Controller)
If your application or cluster resources are managed by ArgoCD, scale down the ArgoCD controllers first. This prevents ArgoCD from auto-syncing or fighting with Velero during the restoration process:

```bash
kubectl scale deployment,statefulset,replicaset --replicas=0 -n argocd --all
```

### 3. Trigger the Cluster Restore
Initiate the restore process by utilizing the exact snapshot name targeted from your search:

```bash
velero restore create --from-backup tools-lubelog-20260713091029 \
  --existing-resource-policy=update \
  --restore-volumes=false \
  --exclude-resources certificaterequests.cert-manager.io,orders.cert-manager.io,orders.acme.cert-manager.io

```

### 4. Track Status & Logs
Monitor the progression of your recovery task until the status reads `Completed`:

```bash
# Check high-level progress
velero restore get

# Review granular configurations and active error tracking
velero restore describe smallstep-smallstep-20260712090027
```

### 5. Restore ArgoCD (Scale Up Controller)
Once the Velero restore is fully complete, restore your ArgoCD controllers back to their functional state to resume normal GitOps management:

```bash
kubectl scale deployment,statefulset,replicaset --replicas=1 -n argocd --all
```