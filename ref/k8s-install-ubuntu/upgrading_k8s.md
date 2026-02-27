# Kubernetes v1.35.1 Upgrade (Single Node - Ubuntu 24.04)

### 1. Update Repository & GPG Key
```bash
## Set the source list to the v1.35 stable path
echo "deb [signed-by=/etc/apt/keyrings/kubernetes-apt-keyring.gpg] https://pkgs.k8s.io/core:/stable:/v1.35/deb/ /" | sudo tee /etc/apt/sources.list.d/kubernetes.list

## Download the specific v1.35 GPG key to fix NO_PUBKEY errors
sudo curl -fsSL https://pkgs.k8s.io/core:/stable:/v1.35/deb/Release.key | sudo gpg --dearmor --yes -o /etc/apt/keyrings/kubernetes-apt-keyring.gpg

## Refresh the package index
sudo apt-get update
```

## Install the v1.35.1 version of kubeadm

```bash
sudo apt-mark unhold kubeadm
sudo apt-get install -y kubeadm=1.35.1-1.1
sudo apt-mark hold kubeadm

# Verify version
kubeadm version -o json
```
## Apply the Cluster Upgrade

```bash
# Plan the upgrade to check for issues
sudo kubeadm upgrade plan

# Apply the upgrade to the control plane components
sudo kubeadm upgrade apply v1.35.1 -y
```
## Upgrade kubelet and kubectl

```bash
sudo apt-mark unhold kubelet kubectl
sudo apt-get install -y kubelet=1.35.1-1.1 kubectl=1.35.1-1.1
sudo apt-mark hold kubelet kubectl
# Verify versions
kubelet --version
kubectl version --client
```
## Restart kubelet to apply changes
```bash
sudo systemctl daemon-reload
sudo systemctl restart kubelet
```
## Verify cluster health
```bash
kubectl get nodes
kubectl get pods -A
```


