# Update the system and install dependencies:
```
sudo apt update && sudo apt upgrade -y
sudo apt install apt-transport-https curl containerd  -y
```

# Configure containerd:
```
sudo mkdir -p /etc/containerd
containerd config default | sudo tee /etc/containerd/config.toml > /dev/null
sudo sed -i 's/SystemdCgroup = false/SystemdCgroup = true/' /etc/containerd/config.toml
sudo systemctl restart containerd
```
# Install runc
```
curl -fsSLo runc.amd64 \
  https://github.com/opencontainers/runc/releases/download/v1.1.3/runc.amd64
sudo install -m 755 runc.amd64 /usr/local/sbin/runc
```
# Install CNI network plugins
```
curl -fLo cni-plugins-linux-amd64-v1.1.1.tgz \
  https://github.com/containernetworking/plugins/releases/download/v1.1.1/cni-plugins-linux-amd64-v1.1.1.tgz
sudo mkdir -p /opt/cni/bin
sudo tar Cxzvf /opt/cni/bin cni-plugins-linux-amd64-v1.1.1.tgz
```

# Install Kubernetes components:
```
REL=v1.31
curl -fsSL https://pkgs.k8s.io/core:/stable:/${REL}/deb/Release.key | sudo gpg --dearmor -o /etc/apt/keyrings/kubernetes-apt-keyring.gpg
echo "deb [signed-by=/etc/apt/keyrings/kubernetes-apt-keyring.gpg] https://pkgs.k8s.io/core:/stable:/${REL}/deb/ /" | sudo tee /etc/apt/sources.list.d/kubernetes.list
sudo apt update
sudo apt install -y kubelet kubeadm kubectl
sudo apt-mark hold kubelet kubeadm kubectl
```
# Disable swap:
```
sudo swapoff -a
sudo sed -i '/ swap / s/^\(.*\)$/#\1/g' /etc/fstab
```

# Add Kernel Parameters (All Nodes)
```
cat <<EOF | sudo tee /etc/modules-load.d/containerd.conf
overlay
br_netfilter
EOF

```
```
sudo modprobe overlay
sudo modprobe br_netfilter        
```

# Set required sysctl parameters:
```
cat <<EOF | sudo tee /etc/sysctl.d/k8s.conf
net.bridge.bridge-nf-call-iptables  = 1
net.bridge.bridge-nf-call-ip6tables = 1
net.ipv4.ip_forward                 = 1
EOF
```

# Reload the changes:
```
sudo sysctl --system    
```

# Initialize the cluster (master)
```
sudo kubeadm init --pod-network-cidr=10.244.0.0/16
```

# set up kubeconfig
```
mkdir -p $HOME/.kube
sudo cp -i /etc/kubernetes/admin.conf $HOME/.kube/config
sudo chown $(id -u):$(id -g) $HOME/.kube/config
```

# Untaint node
```
kubectl taint nodes --all node-role.kubernetes.io/master-
kubectl taint nodes --all node-role.kubernetes.io/control-plane-
```

# Install Flannel network plugin (run only on master node):
```
kubectl apply -f https://github.com/flannel-io/flannel/releases/latest/download/kube-flannel.yml
```

# Install helm
```
curl https://raw.githubusercontent.com/helm/helm/master/scripts/get-helm-3 | bash
```

# Verify
```
kubectl get nodes
kubectl get pods --all-namespaces
```

# Prepare for metallb set mode to ipvs
```
kubectl edit configmap -n kube-system
```
change mode and strictARP
```
apiVersion: kubeproxy.config.k8s.io/v1alpha1
kind: KubeProxyConfiguration
mode: "ipvs"
ipvs:
  strictARP: true
```

```
# see what changes would be made, returns nonzero returncode if different
kubectl get configmap kube-proxy -n kube-system -o yaml | \
sed -e "s/strictARP: false/strictARP: true/" | \
kubectl diff -f - -n kube-system

# actually apply the changes, returns nonzero returncode on errors only
kubectl get configmap kube-proxy -n kube-system -o yaml | \
sed -e "s/strictARP: false/strictARP: true/" | \
kubectl apply -f - -n kube-system
```

# GPU
https://www.jimangel.io/posts/nvidia-rtx-gpu-kubernetes-setup/

```
wget https://us.download.nvidia.com/tesla/550.127.08/nvidia-driver-local-repo-ubuntu2404-550.127.08_1.0-1_amd64.deb
apt install ./nvidia-driver-local-repo-ubuntu2404-550.127.08_1.0-1_amd64.deb 
sudo cp /var/nvidia-driver-local-repo-ubuntu2404-550.127.08/nvidia-driver-local-A0239FBD-keyring.gpg /usr/share/keyrings/
```

```
sudo ubuntu-drivers --gpgpu list
sudo ubuntu-drivers install
