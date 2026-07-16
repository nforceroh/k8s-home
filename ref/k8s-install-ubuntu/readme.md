# virt01 — Kubernetes Setup on Ubuntu 26.04

## System: Dell R730 | Ubuntu 26.04 LTS | kubeadm | single-node | ZFS storage

---

## 1. Remove Unneeded Packages

```bash
# Remove cloud-init
sudo apt purge -y cloud-init
sudo rm -rf /etc/cloud /var/lib/cloud

# Remove snapd completely
sudo systemctl stop snapd
sudo apt purge -y snapd
sudo rm -rf /snap /var/snap /var/lib/snapd /var/cache/snapd ~/snap

# Remove unneeded packages
sudo apt purge -y \
    popularity-contest \
    apport \
    whoopsie \
    motd-news-config \
    ubuntu-advantage-tools

sudo apt autoremove -y
sudo apt autoclean
```

## 2. Prevent snapd from Being Reinstalled

```bash
echo "Package: snapd
Pin: release *
Pin-Priority: -10" | sudo tee /etc/apt/preferences.d/snapd
```

## 3. Disable MOTD News

```bash
sudo rm -f /etc/update-motd.d/50-motd-news
sudo chmod -x /etc/update-motd.d/*
```

## 4. Disable AppArmor

```bash
sudo systemctl stop apparmor
sudo systemctl disable apparmor
sudo apt remove -y apparmor
```

---

## 5. ZFS — Install and Import Pools

```bash
sudo apt install -y zfsutils-linux

# Import pools by name (ZFS uses GUIDs — device names don't matter)
sudo zpool import -f ssd01
sudo zpool import -f hdd01

# Verify both came up clean
sudo zpool status ssd01
sudo zpool status hdd01

# Confirm critical k8s datasets are mounted
df -h | grep -E 'ssd01|hdd01'
# Expected:
#   ssd01/etcd        → /var/lib/etcd
#   ssd01/containerd  → /var/lib/containerd
#   ssd01/kubelet     → /var/lib/kubelet
```

---

## 6. Netplan — VLAN and Bridge Setup

```bash
# Remove installer-generated configs
sudo rm -f /etc/netplan/50-cloud-init.yaml
sudo rm -f /etc/netplan/00-installer-config.yaml

sudo tee /etc/netplan/01-vlan-interfaces.yaml << 'EOF'
network:
  version: 2
  ethernets:
    eno1:
      critical: true
      dhcp-identifier: mac
    eno4:
      critical: true
      dhcp-identifier: mac
  bridges:
    br0:
      interfaces: [eno1]
      dhcp4: no
      dhcp6: no
      accept-ra: false
    br4:
      interfaces: [eno4]
      dhcp4: no
      dhcp6: no
      accept-ra: false
    br1000:
      interfaces: [br0.1000]
      dhcp4: no
      dhcp6: no
      accept-ra: false
    br1400:
      interfaces: [br0.1400]
      dhcp4: no
      dhcp6: no
      accept-ra: false
    br1990:
      interfaces: [br0.1990]
      dhcp4: no
      dhcp6: no
      accept-ra: false
  vlans:
    eno1.1000:
      link: eno1
      id: 1000
      dhcp4: yes
      dhcp6: yes
    br0.1000:
      link: br0
      id: 1000
    br0.1400:
      link: br0
      id: 1400
    br0.1990:
      link: br0 
      id: 1990
EOF

sudo chmod 600 /etc/netplan/01-vlan-interfaces.yaml
sudo netplan try
```

### Fix networkd-wait-online (prevents slow boot with unused NICs)

```bash
sudo systemctl disable systemd-networkd-wait-online.service
sudo systemctl mask systemd-networkd-wait-online.service

# Verify
systemctl status systemd-networkd-wait-online.service
# Should show: Loaded: masked
```

---

## 7. Update System and Install Dependencies

```bash
sudo apt update && sudo apt upgrade -y
sudo apt install -y \
    apt-transport-https \
    ca-certificates \
    curl \
    gnupg \
    conntrack \
    containerd \
    psmisc
```

---

## 8. Configure containerd

```bash
sudo mkdir -p /etc/containerd
containerd config default | sudo tee /etc/containerd/config.toml > /dev/null
sudo sed -i 's/SystemdCgroup = false/SystemdCgroup = true/g' /etc/containerd/config.toml
sudo systemctl restart containerd
sudo systemctl enable containerd

# Verify
sudo systemctl status containerd
```

---

## 9. Disable Swap

```bash
sudo swapoff -a
# Comment out swap line in fstab
sudo sed -i '/ swap / s/^\(.*\)$/#\1/g' /etc/fstab
```

---

## 10. Kernel Modules for Kubernetes Networking

```bash
cat <<EOF | sudo tee /etc/modules-load.d/k8s.conf
overlay
br_netfilter
EOF

sudo modprobe overlay
sudo modprobe br_netfilter
```

---

## 11. sysctl Parameters

```bash
cat <<EOF | sudo tee /etc/sysctl.d/k8s.conf
net.bridge.bridge-nf-call-iptables  = 1
net.bridge.bridge-nf-call-ip6tables = 1
net.ipv4.ip_forward                 = 1
net.ipv6.conf.default.forwarding    = 1
net.ipv6.conf.all.forwarding        = 1
net.core.rmem_max=8388608
net.core.wmem_max=8388608
net.ipv4.tcp_rmem=4096 87380 8388608
net.ipv4.tcp_wmem=4096 87380 8388608
fs.inotify.max_user_watches         = 1048576
fs.inotify.max_user_instances       = 8192
EOF

sudo sysctl --system
```

---

## 12. File Descriptor Limits

```bash
cat <<EOF | sudo tee /etc/security/limits.d/k8s
*         soft    nofile      102400
*         hard    nofile      102400
EOF
```

---

## 12b. Increase Kubelet maxPods (single-node with many workloads)

Default kubelet allows 110 pods per node. For heavily-loaded single-node clusters bump it to 200. This must be set BEFORE `kubeadm init`, or applied AFTER by editing kubelet config and restarting.

### Option A: Pre-init (set in kubeadm config)

Add to your kubeadm-config.yaml:

```yaml
apiVersion: kubelet.config.k8s.io/v1beta1
kind: KubeletConfiguration
maxPods: 200
```

### Option B: Post-init (edit running config)

```bash
# Add maxPods to kubelet config
sudo sed -i '/^kind: KubeletConfiguration/a maxPods: 200' /var/lib/kubelet/config.yaml

# Or if maxPods already exists, update it
sudo sed -i 's/^maxPods:.*/maxPods: 200/' /var/lib/kubelet/config.yaml

# Verify
grep maxPods /var/lib/kubelet/config.yaml

# Restart kubelet
sudo systemctl restart kubelet

# Verify node capacity
kubectl get node virt01 -o jsonpath='{.status.capacity.pods}'
# Should output: 200
```

---

## 13. Verify Prerequisites

```bash
free -h | grep -i swap          # Should show 0B
lsmod | grep -E "overlay|br_netfilter"  # Both modules listed
sysctl net.ipv4.ip_forward      # Should be 1
```

---

## 14. Install Kubernetes v1.36

```bash
REL=v1.36

curl -fsSL https://pkgs.k8s.io/core:/stable:/${REL}/deb/Release.key | \
    sudo gpg --dearmor --yes -o /etc/apt/keyrings/kubernetes-apt-keyring.gpg

echo "deb [signed-by=/etc/apt/keyrings/kubernetes-apt-keyring.gpg] https://pkgs.k8s.io/core:/stable:/${REL}/deb/ /" | \
    sudo tee /etc/apt/sources.list.d/kubernetes.list

sudo apt update
sudo apt install -y kubelet kubeadm kubectl
sudo apt-mark hold kubelet kubeadm kubectl

# Verify
kubeadm version
kubelet --version
kubectl version --client
```

---

## 15. Install Dell racadm (iDRAC management)

```bash
wget -U="Mozilla/5.0 (X11; Linux x86_64; rv:10.0) Gecko/20100101 Firefox/10.0" \
    "https://dl.dell.com/FOLDER08952875M/1/Dell-iDRACTools-Web-LX-11.0.0.0-5139_A00.tar.gz" \
    -O /tmp/idrac.tar.gz
cd /tmp
tar xvfz idrac.tar.gz
cd /tmp/iDRACTools/racadm/UBUNTU22/x86_64
sudo apt install -y libargtable2-0
sudo dpkg -i srvadmin-*.deb
sudo ln -s /opt/dell/srvadmin/bin/idracadm7 /usr/local/bin/racadm
cd /tmp
rm -rf idrac.tar.gz iDRACTools

racadm getsysinfo
```

---

## 16. Install NVIDIA Drivers and Container Toolkit (Tesla P40)

Reference: https://www.jimangel.io/posts/nvidia-rtx-gpu-kubernetes-setup/

### Verify card is detected

```bash
sudo lspci | grep NVI
# Expected: 82:00.0 3D controller: NVIDIA Corporation GP102GL [Tesla P40] (rev a1)
```

### Clean up any old drivers first

```bash
sudo apt-get purge '^nvidia.*' 'libnvidia.*' 'linux-objects-nvidia.*' 'linux-signatures-nvidia.*' 'xserver-xorg-video-nvidia.*' -y
sudo reboot
```

### Check available drivers

```bash
sudo ubuntu-drivers list --gpgpu
```

### Confirmed driver support for P40

- Driver 575+: https://docs.nvidia.com/datacenter/tesla/tesla-release-notes-575-57-08/index.html#hardware-software-support
- Driver 580.95.05: https://docs.nvidia.com/datacenter/tesla/tesla-release-notes-580-95-05/index.html#hardware-software-support

### Install drivers and toolkit

```bash
sudo ubuntu-drivers install nvidia:580-server
sudo apt install -y \
    nvidia-utils-580-server \
    nvidia-container-toolkit \
    nvidia-container-toolkit-base \
    libnvidia-container-tools \
    libnvidia-container1 \
    nvidia-settings \
    nvidia-prime
sudo apt autoremove -y
sudo reboot
```

### List installed NVIDIA packages (for reference)

```bash
dpkg -l | grep nvidia
```

### Configure containerd for NVIDIA runtime

```bash
sudo nvidia-ctk runtime configure --runtime=containerd
sudo systemctl restart containerd
```

### Verify

```bash
nvidia-smi
# Expected output shows Tesla P40, 24576MiB VRAM, driver version 580.x
```

---

## 17. Restore Kubernetes PKI and Initialize Cluster

> **Important:** etcd data is already on ZFS at `/var/lib/etcd` — use `--ignore-preflight-errors=DirAvailable--var-lib-etcd`

```bash
# Restore PKI from ZFS backup
sudo cp -r /mnt/ssd01/os-backup/etc-kubernetes/ /etc/kubernetes/

# Initialize cluster — reusing existing etcd data on ZFS
IP=10.0.0.100

sudo kubeadm init \
    --control-plane-endpoint $IP \
    --pod-network-cidr=10.244.0.0/16,fd00:244::/64 \
    --service-cidr=10.96.0.0/16,fd00:96::/112 \
    --ignore-preflight-errors=DirAvailable--var-lib-etcd

```

---

## 17. Configure kubectl

```bash
mkdir -p $HOME/.kube
sudo cp -i /etc/kubernetes/admin.conf $HOME/.kube/config
sudo chown $(id -u):$(id -g) $HOME/.kube/config
```

---

## 18. Untaint Control Plane (single-node)

```bash
kubectl taint nodes --all node-role.kubernetes.io/control-plane-
kubectl taint nodes --all node-role.kubernetes.io/master- 2>/dev/null || true
```

---

## 19. Install CNI — Calico

```bash
# Install tigera operator
kubectl apply -f https://raw.githubusercontent.com/projectcalico/calico/v3.32.1/manifests/tigera-operator.yaml

# Wait for operator to be ready
kubectl wait --for=condition=available --timeout=120s deployment/tigera-operator -n tigera-operator

# Apply installation CR
kubectl apply -f https://raw.githubusercontent.com/projectcalico/calico/v3.32.1/manifests/custom-resources.yaml

# Watch calico-system come up
kubectl get pods -n calico-system -w
```

# Install calicoctl
```bash
curl -L https://github.com/projectcalico/calico/releases/download/v3.32.1/calicoctl-linux-amd64 \
    -o kubectl-calico
sudo install -m 755 -o root -g root kubectl-calico /usr/local/bin
rm kubectl-calico
```

### Fix Calico RBAC after etcd restore (if restoring from backup)

When restoring from an etcd backup, several stale Calico artifacts cause the tigera-operator to fail with migration errors. The cleanest fix is to fully uninstall and reinstall Calico:

```bash
# Remove finalizers from all calico clusterroles and bindings
for rb in $(kubectl get clusterrolebinding | grep calico | awk '{print $1}'); do
  kubectl patch clusterrolebinding $rb --type=json \
    -p='[{"op":"remove","path":"/metadata/finalizers"}]' 2>/dev/null
  kubectl delete clusterrolebinding $rb --grace-period=0 --force 2>/dev/null
done

for cr in $(kubectl get clusterrole | grep calico | awk '{print $1}'); do
  kubectl patch clusterrole $cr --type=json \
    -p='[{"op":"remove","path":"/metadata/finalizers"}]' 2>/dev/null
  kubectl delete clusterrole $cr --grace-period=0 --force 2>/dev/null
done

# Remove old flannel-migration calico artifacts from kube-system
kubectl delete daemonset -n kube-system calico-node 2>/dev/null
kubectl delete configmap -n kube-system calico-config 2>/dev/null
kubectl delete serviceaccount -n kube-system calico-node 2>/dev/null
kubectl delete serviceaccount -n kube-system calico-cni-plugin 2>/dev/null
kubectl delete serviceaccount -n kube-system calico-kube-controllers 2>/dev/null
kubectl delete rolebinding -n kube-system calico-apiserver-auth-reader 2>/dev/null

# Force delete calico-system namespace
kubectl delete ns calico-system --grace-period=0 --force

# Force delete tigera-operator namespace
kubectl delete all --all -n tigera-operator --grace-period=0 --force
kubectl get crd | grep -E 'tigera|operator.tigera' | awk '{print $1}' | \
  xargs kubectl delete crd --grace-period=0 --force 2>/dev/null
kubectl delete ns tigera-operator --grace-period=0 --force

# If namespaces are stuck Terminating, use proxy to clear finalizers
kubectl proxy &
PROXY_PID=$!
sleep 2
curl -k -H "Content-Type: application/json" -X PUT \
  http://localhost:8001/api/v1/namespaces/tigera-operator/finalize \
  -d '{"apiVersion":"v1","kind":"Namespace","metadata":{"name":"tigera-operator"},"spec":{"finalizers":[]}}'
curl -k -H "Content-Type: application/json" -X PUT \
  http://localhost:8001/api/v1/namespaces/calico-system/finalize \
  -d '{"apiVersion":"v1","kind":"Namespace","metadata":{"name":"calico-system"},"spec":{"finalizers":[]}}'
kill $PROXY_PID

# Reinstall fresh
kubectl apply -f https://raw.githubusercontent.com/projectcalico/calico/v3.32.1/manifests/tigera-operator.yaml
kubectl wait --for=condition=available --timeout=120s deployment/tigera-operator -n tigera-operator

# CRITICAL: Create custom Installation with correct pod CIDR (matches kubeadm --pod-network-cidr)
# Do NOT use the default custom-resources.yaml which uses 192.168.0.0/16
cat <<EOF | kubectl apply -f -
apiVersion: operator.tigera.io/v1
kind: Installation
metadata:
  name: default
spec:
  calicoNetwork:
    ipPools:
    - blockSize: 26
      cidr: 10.244.0.0/16
      encapsulation: VXLANCrossSubnet
      natOutgoing: Enabled
      nodeSelector: all()
EOF

# Watch operator reconcile
kubectl get tigerastatus -w
```

### Troubleshooting: Fix stale RBAC bindings pointing to kube-system

If pods fail with `serviceaccount ... is forbidden` errors after Calico is installed, the ClusterRoleBindings may point to `kube-system` (from the old etcd data) instead of `calico-system`. Bulk fix:

```bash
for rb in $(kubectl get clusterrolebinding | grep calico | awk '{print $1}'); do
  NS=$(kubectl get clusterrolebinding $rb -o jsonpath='{.subjects[0].namespace}' 2>/dev/null)
  if [ "$NS" = "kube-system" ]; then
    echo "Fixing $rb (was kube-system)"
    ROLE=$(kubectl get clusterrolebinding $rb -o jsonpath='{.roleRef.name}')
    SA=$(kubectl get clusterrolebinding $rb -o jsonpath='{.subjects[0].name}')
    kubectl patch clusterrolebinding $rb --type=json \
      -p='[{"op":"remove","path":"/metadata/finalizers"}]' 2>/dev/null
    kubectl delete clusterrolebinding $rb --grace-period=0 --force 2>/dev/null
    kubectl create clusterrolebinding $rb \
      --clusterrole=$ROLE \
      --serviceaccount=calico-system:$SA
  fi
done
```

---

## 20. Install Helm

```bash
curl https://raw.githubusercontent.com/helm/helm/master/scripts/get-helm-3 | bash
```

---

## 21. MetalLB Fix

```bash
kubectl label nodes virt01 node.kubernetes.io/exclude-from-external-load-balancers-
```

---

## 22. Configure kube-proxy for IPVS (MetalLB requirement)

```bash
kubectl get configmap kube-proxy -n kube-system -o yaml | \
    sed -e "s/strictARP: false/strictARP: true/" | \
    kubectl apply -f - -n kube-system

kubectl edit configmap -n kube-system kube-proxy
# Set: mode: "ipvs"  and  strictARP: true
```

---

## 23. Verify

```bash
kubectl get nodes
kubectl get pods --all-namespaces
```

All system pods should show `Running` or `Completed`.
Node should show `Ready`.

---

## 24. ZFS Pool Upgrade (optional — after everything is stable)

```bash
# Upgrades pool feature flags to match new ZFS version
# WARNING: pools will no longer be importable on older ZFS versions after this
sudo zpool upgrade ssd01
sudo zpool upgrade hdd01
```

---

## Reset / Change IP Procedure (for reference)

```bash
IP=10.0.0.100

systemctl stop kubelet containerd

mv -f /etc/kubernetes /etc/kubernetes-backup
mv -f /var/lib/kubelet /var/lib/kubelet-backup

mkdir -p /etc/kubernetes
cp -r /etc/kubernetes-backup/pki /etc/kubernetes
rm -rf /etc/kubernetes/pki/{apiserver.*,etcd/peer.*}

systemctl start containerd

kubeadm init \
    --control-plane-endpoint $IP \
    --pod-network-cidr=10.244.0.0/16,2001:db8:42:0::/56 \
    --service-cidr=10.96.0.0/16,2001:db8:42:1::/112 \
    --ignore-preflight-errors=DirAvailable--var-lib-etcd
```

