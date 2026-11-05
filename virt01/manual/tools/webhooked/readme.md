# Webhooked

Webhooked captures generic HTTP requests at per-integration UUIDv4 URLs and
provides a private UI to inspect and export deliveries. It is deployed
manually in the `tools` namespace and is available on the internal network
at [https://webhooked.k3s.nf.lab](https://webhooked.k3s.nf.lab). The Ingress
uses the `nf-lab` certificate issuer and points DNS to
`traefik.k3s.nf.lab`.

The app has no UI login; expose it only on a trusted homelab network. The
UUID in a capture URL is a write capability, not proof of sender identity.
Do not send credentials or sensitive production data to this service.

The app uses SQLite at `/data/db.sqlite3`, persisted on the `webhooked-data`
PVC. It runs as a single replica with `strategy: Recreate` because SQLite
locking is unreliable across multiple pods and on NFS-backed storage.

## Create the secret key

Webhooked requires a stable `DJANGO_SECRET_KEY`. If it is unset, a random key
is generated on every start, which invalidates sessions and CSRF tokens
across restarts. Generate it once and store it as a SealedSecret in the
private `k8s-home-secrets` repository; do not commit the plaintext key here.
This command assumes `kubeseal` is configured for the cluster:

```bash
set -eu
SECRET_DIR="$HOME/repositories/k8s-home-secrets/webhooked"
SECRET_FILE="$SECRET_DIR/webhooked-config-sealed.yaml"
KEY_FILE="$(mktemp)"
trap 'rm -f "$KEY_FILE"' EXIT

mkdir -p "$SECRET_DIR"
if [ -e "$SECRET_FILE" ]; then
  echo "Sealed secret already exists $SECRET_FILE; do not replace the DJANGO_SECRET_KEY."
  exit 1
fi

umask 077
printf '%s' "$(openssl rand -base64 48)" > "$KEY_FILE"
kubectl create secret generic webhooked-config \
  --namespace=tools \
  --from-file=DJANGO_SECRET_KEY="$KEY_FILE" \
  --dry-run=client -o yaml |
  kubeseal --cert "$HOME/repositories/k8s-home-secrets/sealed-secrets/nf-lab.crt" --scope cluster-wide --format=yaml > "$SECRET_FILE"

git -C "$HOME/repositories/k8s-home-secrets" add webhooked/webhooked-config-sealed.yaml
git -C "$HOME/repositories/k8s-home-secrets" commit -m "Add webhooked secret key"
git -C "$HOME/repositories/k8s-home-secrets" push
kubectl apply -f "$SECRET_FILE"
```

Keep the same key across upgrades and restores. If a replacement is required,
update the SealedSecret in the private repository and apply it before
restarting the app.

## Deploy

Apply the app manifests after the `webhooked-config` Secret exists:

```bash
kubectl apply -k "$HOME/repositories/k8s-home/virt01/manual/tools/webhooked"
kubectl wait -n tools --for=condition=Ready pvc/webhooked-data --timeout=5m
kubectl get pods -n tools -l app=webhooked
kubectl wait -n tools --for=condition=Ready certificate/webhooked-tls --timeout=5m
```

The container applies migrations before starting Gunicorn on port 8000.
Health checks are available at `/health/live` and `/health/ready`.
