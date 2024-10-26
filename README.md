# k8s-home

# set up harvester hci

# set up talos single node cluster
# pxe setup
# boot
# config node
factory.talos.dev/installer/a28d86375cf9debe952efbcbe8e2886cf0a174b1f4dd733512600a40334977d7:v1.8.1
```
export CLUSTER_NAME=talos
export NODEIP=10.0.0.226
export API_ENDPOINT=https://${NODEIP}:6443

talosctl gen secrets --output-file secrets.yaml --force

talosctl gen config $CLUSTER_NAME $API_ENDPOINT --with-secrets ./secrets.yaml

talosctl gen config $CLUSTER_NAME $API_ENDPOINT -o $HOME/.talos/

talosctl config endpoint ${NODEIP}
talosctl config node ${NODEIP}



talosctl gen config \
  --output rendered/node01.yaml                                 \
  --output-types controlplane                               \
  --with-secrets secrets.yaml                               \
  --config-patch @patches/cluster-name.yaml                 \
  --config-patch @patches/extramanifests.yaml   \
  --config-patch @patches/allow-controlplane-workloads.yaml \
  --config-patch @patches/metrics.yaml \
  --config-patch @nodes/node01.yaml                             \
  $CLUSTER_NAME $API_ENDPOINT --force


talosctl apply-config -n ${NODEIP} -e ${NODEIP} --file rendered/node01.yaml --insecure

talosctl apply-config --insecure -n ${NODEIP} --file  $HOME/.talos/controlplane.yaml 


talosctl bootstrap -n ${NODEIP} -e  ${NODEIP} --talosconfig ./talosconfig 
talosctl --talosconfig=./talosconfig config endpoint 10.0.0.226
talosctl --talosconfig=./talosconfig config node 10.0.0.226
talosctl config merge $HOME/.talos/config  --talosconfig ./talosconfig 

talosctl get members -n ${NODEIP} -e  ${NODEIP} --talosconfig ./talosconfig 


talosctl kubeconfig ~/.kube/talos -n ${NODEIP} -e  ${NODEIP} --talosconfig ./talosconfig 
export KUBECONFIG=~/.kube/talos

sylvain@MasterSim:~/gitdev/k8s-home$ kubectl get nodes
NAME    STATUS   ROLES           AGE     VERSION
talos   Ready    control-plane   4m53s   v1.31.1

```



# bootstrap argocd...

