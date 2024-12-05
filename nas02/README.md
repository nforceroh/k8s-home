# k8s-home

# set up harvester hci

# set up talos single node cluster
# pxe setup
# boot
# config node



# bootstrap argocd...

# kubeseal
```
# https://github.com/bitnami-labs/sealed-secrets/blob/main/docs/bring-your-own-certificates.md
# generate own cert
export PRIVATEKEY="mytls.key"
export PUBLICKEY="mytls.crt"
export NAMESPACE="sealed-secrets"
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