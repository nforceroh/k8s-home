# netplan setup for vlan trunks
https://michaelwaterman.nl/2023/12/12/advanced-netplan-config-on-ubuntu/
```
network:
  version: 2
  ethernets:
    eno1:
      critical: true
      dhcp-identifier: mac
  bridges:
    br0:
      interfaces: [eno1]
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
```



# Update the system and install dependencies:
```
sudo apt update && sudo apt upgrade -y
sudo apt install apt-transport-https curl containerd psmisc -y
```

# disable AppArmor
```
sudo systemctl stop apparmor
sudo systemctl disable apparmor
sudo apt remove apparmor -y
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
net.core.rmem_max=8388608
net.core.wmem_max=8388608
net.ipv4.tcp_rmem=4096 87380 8388608
net.ipv4.tcp_wmem=4096 87380 8388608
EOF
```

# Set limits
```
cat <<EOF | sudo tee /etc/security/limits.d/k8s
*         soft    nofile      102400
*         hard    nofile      102400
EOF
```

# Reload the changes:
```
sudo sysctl --system    
```

# Initialize the cluster (master)
```
sudo kubeadm init --pod-network-cidr=10.244.0.0/16,2001:db8:42:0::/56 --service-cidr=10.96.0.0/16,2001:db8:42:1::/112 
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

# Metallb fix
```
kubectl label nodes virt01 node.kubernetes.io/exclude-from-external-load-balancers-
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


# 550
```bash
wget https://us.download.nvidia.com/tesla/550.127.08/nvidia-driver-local-repo-ubuntu2404-550.127.08_1.0-1_amd64.deb
apt install ./nvidia-driver-local-repo-ubuntu2404-550.127.08_1.0-1_amd64.deb 
sudo cp /var/nvidia-driver-local-repo-ubuntu2404-550.127.08/nvidia-driver-local-A0239FBD-keyring.gpg /usr/share/keyrings/
```

# 570

```bash
wget https://us.download.nvidia.com/tesla/570.133.20/nvidia-driver-local-repo-ubuntu2404-570.133.20_1.0-1_amd64.deb
apt install ./nvidia-driver-local-repo-ubuntu2404-570.133.20_1.0-1_amd64.deb
sudo cp /var/nvidia-driver-local-repo-ubuntu2404-570.133.20/nvidia-driver-local-BB6607B3-keyring.gpg /usr/share/keyrings/
```

```
sudo ubuntu-drivers --gpgpu list
sudo ubuntu-drivers install


# Reset certs/change IP
```
# Set IP Var
IP=10.0.0.100
 
# Stop Services
systemctl stop kubelet containerd
 
# Backup Kubernetes and kubelet
mv -f /etc/kubernetes /etc/kubernetes-backup
mv -f /var/lib/kubelet /var/lib/kubelet-backup
 
# Keep the certs we need
mkdir -p /etc/kubernetes
cp -r /etc/kubernetes-backup/pki /etc/kubernetes
rm -rf /etc/kubernetes/pki/{apiserver.*,etcd/peer.*}
 
# Start docker
systemctl start containerd
 
# Init cluster with new ip address
IP=10.0.0.100
kubeadm init --control-plane-endpoint $IP --pod-network-cidr=10.244.0.0/16,2001:db8:42:0::/56 --service-cidr=10.96.0.0/16,2001:db8:42:1::/112 --ignore-preflight-errors=DirAvailable--var-lib-etcd
```