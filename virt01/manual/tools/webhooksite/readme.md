# Webhook.site

Webhook.site is deployed manually in the `tools` namespace and is available on
the internal network at [https://webhook.k3s.nf.lab](https://webhook.k3s.nf.lab).
The Ingress uses the `nf-lab` certificate issuer and is not exposed through the
public `nforcer.com` zone.

The app uses its bundled SQLite database for captured requests, persisted on
the `webhooksite-data` PVC. Redis supports the queue, cache, and live updates;
Laravel Echo serves live updates through the app's `/socket.io` proxy. Captures
are retained until deleted in the UI or the PVC is removed. Do not send
credentials or sensitive production data to this troubleshooting service.

## Create the app key

Webhook.site requires a stable Laravel `APP_KEY`. Generate it once and store it
as a SealedSecret in the private `k8s-home-secrets` repository; do not commit
the plaintext key here. This command assumes `kubeseal` is configured for the
cluster:

```bash
set -eu
SECRET_DIR="$HOME/repositories/k8s-home-secrets/webhooksite"
SECRET_FILE="$SECRET_DIR/webhooksite-config-sealed.yaml"
KEY_FILE="$(mktemp)"
trap 'rm -f "$KEY_FILE"' EXIT

mkdir -p "$SECRET_DIR"
if [ -e "$SECRET_FILE" ]; then
  echo "Sealed secret already exists $SECRET_FILE; do not replace the APP_KEY."
  exit 1
fi

umask 077
printf 'base64:%s' "$(openssl rand -base64 32)" > "$KEY_FILE"
kubectl create secret generic webhooksite-config \
  --namespace=tools \
  --from-file=APP_KEY="$KEY_FILE" \
  --dry-run=client -o yaml |
  kubeseal --cert "$HOME/repositories/k8s-home-secrets/sealed-secrets/nf-lab.crt" --scope cluster-wide --format=yaml > "$SECRET_FILE"

git -C "$HOME/repositories/k8s-home-secrets" add webhooksite/webhooksite-config-sealed.yaml
git -C "$HOME/repositories/k8s-home-secrets" commit -m "Add webhook.site app key"
git -C "$HOME/repositories/k8s-home-secrets" push
kubectl apply -f "$SECRET_FILE"
```

Keep the same key across upgrades and restores. If a replacement is required,
update the SealedSecret in the private repository and apply it before restarting
the app.

## Deploy

Apply the app manifests after the `webhooksite-config` Secret exists:

```bash
kubectl apply -k "$HOME/repositories/k8s-home/virt01/manual/tools/webhooksite"
kubectl wait -n tools --for=condition=Ready pvc/webhooksite-data --timeout=5m
kubectl get pods -n tools -l app=webhooksite
kubectl wait -n tools --for=condition=Ready certificate/webhooksite-tls --timeout=5m
```

The init containers initialize the persistent database from the image's
pre-migrated SQLite database and apply any pending migrations before the app
starts. The app uses a single replica because SQLite is not intended for
concurrent writers across multiple pods.
