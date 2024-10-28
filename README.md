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
  --config-patch @patches/cache_registry.yaml \
  --config-patch @patches/trust_nf.lab.yaml \
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

# kubeseal
```
# https://github.com/bitnami-labs/sealed-secrets/blob/main/docs/bring-your-own-certificates.md
# generate own cert
export PRIVATEKEY="mytls.key"
export PUBLICKEY="mytls.crt"
export NAMESPACE="common"
export SECRETNAME="mycustomkeys"
openssl req -x509 -days 3650 -nodes -newkey rsa:4096 -keyout "$PRIVATEKEY" -out "$PUBLICKEY" -subj "/CN=sealed-secret/O=sealed-secret"

# Create a tls k8s secret, using your recently created RSA key pair
kubectl -n "$NAMESPACE" create secret tls "$SECRETNAME" --cert="$PUBLICKEY" --key="$PRIVATEKEY"
kubectl -n "$NAMESPACE" label secret "$SECRETNAME" sealedsecrets.bitnami.com/sealed-secrets-key=active

# Deleting the controller Pod is needed to pick the new keys
kubectl -n  "$NAMESPACE" delete pod -l app.kubernetes.io/name=sealed-secrets

# See the new certificates (private keys) in the controller logs
kubectl -n "$NAMESPACE" logs -l app.kubernetes.io/name=sealed-secrets

wget https://github.com/bitnami-labs/sealed-secrets/releases/download/v0.27.1/kubeseal-0.27.1-linux-amd64.tar.gzta
sudo install -m 755 kubeseal /usr/local/bin/kubeseal
```
kubeseal  --controller-name sealed-secrets --controller-namespace common

kubectl create -f cert-manager.yaml -o yaml --dry-run=client|kubeseal --controller-name sealed-secrets --controller-namespace common > cert-manager-sealed.yaml

Fix UNBOUND PV

for p in `oc get pv|grep pvc|awk '{print $1}'`; do oc patch pv $p -p '{"spec":{"claimRef":{"uid":null}}}';done
Fix Lost PVC

oc get pvc -A|grep -v NAMES|grep Lost|awk '{print "oc annotate pvc "$2" -n "$1" pv.kubernetes.io/bind-completed-"}'