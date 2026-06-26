# Kubernetes Upgrade Runbook (Single Node, Ubuntu 24.04)

Use one variable for the target Kubernetes version, then run the commands in order.

## 0. Copy-safe terminal usage

- Paste only command lines, not the markdown fence lines (` ```bash ` or ` ``` `).
- If your shell prompt changes to `>`, cancel with `Ctrl+C` and re-run the command.
- Keep all version variable commands in the same shell session.

## 1. Discover the newest available version

Run these commands to see the newest package version available from your configured Kubernetes apt repository.

```bash
sudo apt-get update

# Show available kubeadm versions in the repo
apt-cache madison kubeadm

# Print the newest available deb version
LATEST_K8S_DEB_VERSION="$(apt-cache madison kubeadm | awk '{print $3}' | head -n 1)"
echo "${LATEST_K8S_DEB_VERSION}"

# Optional: convert to kubeadm upgrade apply format
LATEST_K8S_VERSION="${LATEST_K8S_DEB_VERSION%-*}"
echo "v${LATEST_K8S_VERSION}"
```

## 2. Set target version

```bash
# Example target version (edit this)
TARGET_K8S_VERSION="1.36.2"

# Derived values (do not edit)
TARGET_K8S_MINOR="${TARGET_K8S_VERSION%.*}"
TARGET_K8S_DEB_VERSION="${TARGET_K8S_VERSION}-1.1"

# Safety check: fail early if any variable is empty
: "${TARGET_K8S_VERSION:?TARGET_K8S_VERSION is required}"
: "${TARGET_K8S_MINOR:?TARGET_K8S_MINOR is required}"
: "${TARGET_K8S_DEB_VERSION:?TARGET_K8S_DEB_VERSION is required}"
```

## 3. Pre-checks

```bash
kubectl get nodes -o wide
kubectl version --client
kubeadm version -o short
kubectl get node "$(kubectl get nodes -o jsonpath='{.items[0].metadata.name}')" -o jsonpath='{.status.capacity.pods}{"\n"}'
```

Notes:
- Upgrade one minor version at a time (for example, 1.34 -> 1.35).
- This runbook is for a single-node cluster: draining the only node is optional and causes a full workload outage during the upgrade.
- Expect a short API/control-plane interruption while static pods are restarted.
- For multi-node clusters, drain workloads from each node before upgrading that node.
- kubeadm-managed kubelet config may reset `maxPods` to the default (`110`) unless you reapply your custom value.

Optional variable for custom pod density:

```bash
# Set only if you want non-default max pods per node
# TARGET_MAX_PODS="250"
```

## 4. Pre-upgrade certificate and backup safety

```bash
# Check certificate expiry before upgrade
sudo kubeadm certs check-expiration

# Optional: renew any expiring certs before upgrade
# sudo kubeadm certs renew all

# Timestamped backup directory
BACKUP_DIR="/root/k8s-upgrade-backup-$(date +%F-%H%M%S)"
sudo mkdir -p "${BACKUP_DIR}"

# Backup critical kubeadm inputs and PKI/manifests
sudo cp -a /etc/kubernetes "${BACKUP_DIR}/etc-kubernetes"
kubectl -n kube-system get configmap kubeadm-config -o yaml | sudo tee "${BACKUP_DIR}/kubeadm-config.yaml" >/dev/null

# Save current component versions and node state
kubectl get nodes -o wide | sudo tee "${BACKUP_DIR}/nodes.txt" >/dev/null
kubectl get pods -A -o wide | sudo tee "${BACKUP_DIR}/pods.txt" >/dev/null

echo "Backup written to ${BACKUP_DIR}"
```

Notes:
- If `kubeadm certs check-expiration` shows already expired etcd or apiserver-etcd-client certs, renew them before running `kubeadm upgrade apply`.
- Keep this backup until the cluster is stable after upgrade.

### Guardrail: verify kubeadm-config does not force wrong etcd certs or invalid extraArgs

If `kubeadm upgrade apply` keeps rewriting kube-apiserver with `--etcd-certfile=/etc/kubernetes/pki/etcd/server.crt` and `--etcd-keyfile=/etc/kubernetes/pki/etcd/server.key`, fix `kubeadm-config` first.

```bash
# Inspect ClusterConfiguration stored in kubeadm-config
kubectl -n kube-system get configmap kubeadm-config -o yaml > /root/kubeadm-config.cm.yaml
grep -nE 'ClusterConfiguration|apiServer|extraArgs|etcd-certfile|etcd-keyfile|certFile|keyFile|external:' /root/kubeadm-config.cm.yaml

# In ClusterConfiguration, ensure etcd.external uses the apiserver etcd client certs:
#   certFile: /etc/kubernetes/pki/apiserver-etcd-client.crt
#   keyFile: /etc/kubernetes/pki/apiserver-etcd-client.key
#
# If apiServer.extraArgs exists in kubeadm.k8s.io/v1beta4 config, it must be a list of
# {name, value} entries, not a key/value map.
kubectl -n kube-system edit configmap kubeadm-config
```

After editing, re-run:

```bash
sudo kubeadm upgrade apply "v${TARGET_K8S_VERSION}" -y --ignore-preflight-errors=CreateJob
```

## 5. Optional: drain the single node before upgrade

If you want fewer running workloads during the control-plane restart and you accept a full outage for application pods, drain the node before `kubeadm upgrade apply`.

```bash
NODE_NAME="$(kubectl get nodes -o jsonpath='{.items[0].metadata.name}')"
echo "${NODE_NAME}"

kubectl drain "${NODE_NAME}" \
	--ignore-daemonsets \
	--delete-emptydir-data \
	--force
```

Notes:
- On a single-node cluster, this evicts normal workloads but DaemonSets and static pods remain.
- If PodDisruptionBudgets block the drain, either relax them temporarily or skip this step.
- Uncordon the node after the upgrade is complete.

## 6. Point apt repo to target minor and refresh key

If you previously wrote an invalid URL like `.../stable:/v/deb/`, repair it first:

```bash
sudo rm -f /etc/apt/sources.list.d/kubernetes.list
```

```bash
: "${TARGET_K8S_MINOR:?Set TARGET_K8S_MINOR before running this step}"

sudo mkdir -p /etc/apt/keyrings

echo "deb [signed-by=/etc/apt/keyrings/kubernetes-apt-keyring.gpg] https://pkgs.k8s.io/core:/stable:/v${TARGET_K8S_MINOR}/deb/ /" \
	| sudo tee /etc/apt/sources.list.d/kubernetes.list >/dev/null

curl -fsSL "https://pkgs.k8s.io/core:/stable:/v${TARGET_K8S_MINOR}/deb/Release.key" \
	| sudo gpg --dearmor --yes -o /etc/apt/keyrings/kubernetes-apt-keyring.gpg

sudo apt-get update
```

## 7. Upgrade kubeadm

```bash
# If the exact target deb version is not available, pick the newest patch in the target minor.
if ! apt-cache madison kubeadm | awk '{print $3}' | grep -qx "${TARGET_K8S_DEB_VERSION}"; then
	TARGET_K8S_DEB_VERSION="$(apt-cache madison kubeadm | awk '{print $3}' | grep -E "^${TARGET_K8S_MINOR//./\\.}\\." | head -n 1)"
	TARGET_K8S_VERSION="${TARGET_K8S_DEB_VERSION%-*}"
	echo "Requested version not found in repo, using ${TARGET_K8S_VERSION} (${TARGET_K8S_DEB_VERSION})"
fi

sudo apt-mark unhold kubeadm
sudo apt-get install -y "kubeadm=${TARGET_K8S_DEB_VERSION}"
sudo apt-mark hold kubeadm

kubeadm version -o short
```

Notes:
- `kubeadm` must already be on the same target minor version as `TARGET_K8S_VERSION` before you run `kubeadm upgrade apply`.
- Example: to upgrade the cluster to `1.36.2`, the installed `kubeadm` binary must first be `v1.36.2`.
- If the exact package does not exist (for example `1.36.2-1.1`), this step automatically switches to the newest available `1.36.x` package and updates `TARGET_K8S_VERSION` accordingly.


## 8. Plan and apply control-plane upgrade

```bash
sudo kubeadm upgrade plan
sudo kubeadm upgrade apply "v${TARGET_K8S_VERSION}" -y --ignore-preflight-errors=CreateJob
```

Notes:
- On this single-node cluster, `CreateJob` may time out even when the cluster is otherwise healthy. The flag above matches the recovery path that worked here.
- If the apply fails, compare the live manifest and generated manifest for `kube-apiserver` and confirm the etcd client cert paths still point to `apiserver-etcd-client.crt` and `apiserver-etcd-client.key`.

## 9. Upgrade kubelet and kubectl

```bash
sudo apt-mark unhold kubelet kubectl
sudo apt-get install -y "kubelet=${TARGET_K8S_DEB_VERSION}" "kubectl=${TARGET_K8S_DEB_VERSION}"
sudo apt-mark hold kubelet kubectl
```

## 10. Restart kubelet

```bash
sudo systemctl daemon-reload

# Optional: reapply custom kubelet maxPods if set
if [[ -n "${TARGET_MAX_PODS:-}" ]]; then
	sudo sed -i '/^maxPods:/d' /var/lib/kubelet/config.yaml
	echo "maxPods: ${TARGET_MAX_PODS}" | sudo tee -a /var/lib/kubelet/config.yaml >/dev/null
fi

sudo systemctl restart kubelet
```

## 11. Verify cluster health

```bash
kubectl get nodes -o wide
kubectl get pods -A
kubelet --version
kubectl version --client
kubectl get node "$(kubectl get nodes -o jsonpath='{.items[0].metadata.name}')" -o jsonpath='{.status.capacity.pods}{"\n"}'
kubectl uncordon "${NODE_NAME:-$(kubectl get nodes -o jsonpath='{.items[0].metadata.name}')}"
```

## 12. Optional quick rollback signal

If pods fail to recover, check:

```bash
kubectl get events -A --sort-by=.lastTimestamp | tail -n 50
journalctl -u kubelet -n 200 --no-pager
```

## 13. Optional containerd cleanup

### 1. Check current usage

```bash
sudo du -sh /var/lib/containerd
sudo crictl images | wc -l
sudo crictl ps -a | wc -l
```

### 2. Remove exited containers and stale pod sandboxes

```bash
sudo crictl ps -a --state Exited -q | xargs -r sudo crictl rm
sudo crictl pods --state NotReady -q | xargs -r sudo crictl rmp
```

### 3. Prune unused images

```bash
sudo crictl rmi --prune
```

### 4. Restart runtime services

```bash
sudo systemctl restart containerd
sudo systemctl restart kubelet
```

### 5. Re-check space

```bash
sudo du -sh /var/lib/containerd
kubectl get nodes -o wide
```


