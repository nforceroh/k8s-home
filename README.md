# k8s-home

# set up harvester hci

# set up talos single node cluster
# pxe setup
# boot
# config node
```
export TALOS_CLUSTER_NAME=test
export NODEIP="10.0.0.226"
talosctl gen config $TALOS_CLUSTER_NAME https://${NODEIP}:6443 -o $HOME/.talos/

talosctl apply-config --insecure -n ${NODEIP} --file controlplane.yaml 
talosctl config merge $HOME/.talos/talosconfig^
talosctl config endpoint ${NODEIP}
talosctl config node ${NODEIP}
talosctl bootstrap

talosctl get members

talosctl kubeconfig ~/.kube/talos
export KUBECONFIG=~/.kube/talos

sylvain@MasterSim:~/gitdev/k8s-home$ kubectl get nodes
NAME    STATUS   ROLES           AGE     VERSION
talos   Ready    control-plane   4m53s   v1.31.1

```

# bootstrap argocd...

