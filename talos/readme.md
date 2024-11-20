factory.talos.dev/installer/a28d86375cf9debe952efbcbe8e2886cf0a174b1f4dd733512600a40334977d7:v1.8.1

https://factory.talos.dev/?arch=amd64&board=undefined&cmdline-set=true&extensions=-&extensions=siderolabs%2Fcrun&extensions=siderolabs%2Fintel-ucode&extensions=siderolabs%2Fiscsi-tools&extensions=siderolabs%2Fnvidia-container-toolkit-production&extensions=siderolabs%2Fnvidia-open-gpu-kernel-modules-production&extensions=siderolabs%2Futil-linux-tools&platform=metal&target=metal&version=1.8.3

```
export CLUSTER_NAME=talos
export NODEIP=192.168.101.100
export API_ENDPOINT=https://${NODEIP}:6443

# For new cluster
talosctl gen secrets --output-file secrets.yaml --force
talosctl gen config $CLUSTER_NAME $API_ENDPOINT --with-secrets ./secrets.yaml


# continue
talosctl gen config $CLUSTER_NAME $API_ENDPOINT -n ${NODEIP} -e  ${NODEIP} -o ./ --force
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

talosctl apply-config -n ${NODEIP} -e ${NODEIP} --file rendered/node01.yaml --insecure

talosctl bootstrap -n ${NODEIP} -e  ${NODEIP} --talosconfig ./talosconfig 
talosctl config merge $HOME/.talos/config  --talosconfig ./talosconfig 

talosctl get members -n ${NODEIP} -e  ${NODEIP} --talosconfig ./talosconfig 


talosctl kubeconfig ~/.kube/talos -n ${NODEIP} -e  ${NODEIP} --talosconfig ./talosconfig 
export KUBECONFIG=~/.kube/talos

sylvain@MasterSim:~/gitdev/k8s-home$ kubectl get nodes
NAME    STATUS   ROLES           AGE     VERSION
talos   Ready    control-plane   4m53s   v1.31.1

```
