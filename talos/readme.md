factory.talos.dev/installer/a28d86375cf9debe952efbcbe8e2886cf0a174b1f4dd733512600a40334977d7:v1.8.1

https://factory.talos.dev/?arch=amd64&board=undefined&cmdline-set=true&extensions=-&extensions=siderolabs%2Fcrun&extensions=siderolabs%2Fintel-ucode&extensions=siderolabs%2Fiscsi-tools&extensions=siderolabs%2Fnvidia-container-toolkit-production&extensions=siderolabs%2Fnvidia-open-gpu-kernel-modules-production&extensions=siderolabs%2Futil-linux-tools&platform=metal&target=metal&version=1.8.3

```
export CLUSTER_NAME=talos
export NODEIP=10.0.0.100
export API_ENDPOINT=https://${NODEIP}:6443

# For new cluster, need to create secrets
talosctl gen config $CLUSTER_NAME $API_ENDPOINT  --force
talosctl gen secrets --output-file secrets.yaml --force

# For consistent cluster config, reuse an existing secret so we don't need to change all our .kube/config
talosctl gen config \
  --with-secrets ./secrets.yaml \
  --output-types talosconfig    \
  --output talosconfig          \
  $CLUSTER_NAME $API_ENDPOINT   --force

talosctl config merge ./talosconfig 

talosctl config endpoint ${NODEIP} --talosconfig ./talosconfig 
talosctl config node ${NODEIP} --talosconfig ./talosconfig 

talosctl gen config \
  --output rendered/node01.yaml               \
  --output-types controlplane                 \
  --with-secrets secrets.yaml                 \
  --config-patch @patches/cluster-config.yaml \
  --config-patch @patches/cache_registry.yaml \
  --config-patch @patches/trust_nf.lab.yaml   \
  --config-patch @patches/metrics.yaml        \
  --config-patch @nodes/node01.yaml           \
  $CLUSTER_NAME $API_ENDPOINT --force


talosctl gen config \
  --output rendered/node01.yaml               \
  --output-types controlplane                 \
  --config-patch @patches/cluster-config.yaml \
  --config-patch @patches/cache_registry.yaml \
  --config-patch @patches/trust_nf.lab.yaml   \
  --config-patch @patches/metrics.yaml        \
  --config-patch @nodes/node01.yaml           \
  $CLUSTER_NAME $API_ENDPOINT --force


talosctl apply-config -n ${NODEIP} --file rendered/node01.yaml --insecure

# needed if first member
talosctl bootstrap -n ${NODEIP} -e  ${NODEIP} --talosconfig ./talosconfig 

talosctl config merge $HOME/.talos/config  --talosconfig ./talosconfig 

talosctl get members -n ${NODEIP} -e  ${NODEIP} --talosconfig ./talosconfig 

mkdir ~/.talos
cp ./talosconfig  ~/.talos/config

talosctl kubeconfig ~/.kube/talos -n ${NODEIP} -e  ${NODEIP} --talosconfig ./talosconfig 
export KUBECONFIG=~/.kube/talos

sylvain@MasterSim:~/gitdev/k8s-home$ kubectl get nodes
NAME    STATUS   ROLES           AGE     VERSION
talos   Ready    control-plane   4m53s   v1.31.1

```

# Install kubevirt
```
export RELEASE=$(curl https://storage.googleapis.com/kubevirt-prow/release/kubevirt/kubevirt/stable.txt)
kubectl create ns kubevirt
kubectl -n kubevirt create -f https://github.com/kubevirt/kubevirt/releases/download/$RELEASE/kubevirt-operator.yaml
kubectl create -f https://github.com/kubevirt/kubevirt/releases/download/$RELEASE/kubevirt-cr.yaml
kubectl -n kubevirt wait kv kubevirt --for condition=Available
kubectl get po -n kubevirt
```
