# OpenBao Manual Helm Deployment

This directory contains a single-replica OpenBao Helm deployment for homelab testing. It uses integrated Raft storage, OpenBao's built-in static-key auto-unseal, and a Traefik Ingress. The OpenBao Service remains ClusterIP; use `kubectl port-forward` for direct troubleshooting access.

Traefik publishes `https://openbao.nf.lab`. cert-manager issues the server certificate from the existing `nf-lab` ClusterIssuer and writes it to the `openbao-tls` Secret used by the Ingress. Traefik terminates external TLS and connects to OpenBao over HTTP on port `8200` inside the cluster. Clients must trust the `nf-lab` CA certificate.

## What must be backed up

OpenBao does not create the static seal key. Generate it once, keep the same key and `current_key_id`, and make a backup before initializing OpenBao.

Keep these items in the private [`k8s-home-secrets`](https://github.com/nforceroh/k8s-home-secrets) repository:

- `openbao/static-unseal.key` - the 32-byte static seal key
- Raft snapshots - OpenBao's encrypted stored data
- Recovery keys from `bao operator init`
- The initial root token, or recovery keys sufficient to generate a replacement token

The Helm values and static seal configuration are in this public repository. The key itself must not be added here.

## Create and save the static seal key

Run this once on a trusted workstation with OpenSSL and the private repository cloned at `~/repositories/k8s-home-secrets`. The check prevents accidentally replacing an existing key.

```bash
set -eu
KEY_DIR="$HOME/repositories/k8s-home-secrets/openbao"
KEY_FILE="$KEY_DIR/static-unseal.key"

mkdir -p "$KEY_DIR"
if [ -e "$KEY_FILE" ]; then
  echo "Key already exists; do not replace it."
  exit 1
fi

umask 077
openssl rand -out "$KEY_FILE" 32
chmod 600 "$KEY_FILE"
test "$(wc -c < "$KEY_FILE")" -eq 32

git -C "$HOME/repositories/k8s-home-secrets" add openbao/static-unseal.key
git -C "$HOME/repositories/k8s-home-secrets" commit -m "Add OpenBao static seal key"
git -C "$HOME/repositories/k8s-home-secrets" push
```

This is a raw 32-byte file; do not open and resave it in a text editor. Keep the private repository private.

## Agent injector

The OpenBao Agent Injector is disabled in [`values.yaml`](./values.yaml). This avoids a server-side-apply ownership conflict on its mutating webhook during Helm upgrades. It also means pods cannot use OpenBao Agent Injector annotations to inject secrets. This is separate from TLS certificate issuance: cert-manager still issues the Ingress certificate, and the injector is not needed for that.

## Install and initialize

Build the chart dependency, create the Kubernetes Secret from that same file, then install the Helm chart. The chart creates the Ingress, and cert-manager's ingress-shim creates the certificate from its annotations:

```bash
KEY_FILE="$HOME/repositories/k8s-home-secrets/openbao/static-unseal.key"
CHART_DIR="$HOME/repositories/k8s-home/virt01/manual/tools/openbao"

helm dependency build "$CHART_DIR"
kubectl create namespace tools --dry-run=client -o yaml | kubectl apply -f -
kubectl create secret generic openbao-static-seal \
  --namespace tools \
  --from-file=unseal.key="$KEY_FILE" \
  --dry-run=client -o yaml | kubectl apply -f -

helm upgrade --install openbao "$CHART_DIR" --namespace tools
kubectl wait -n tools --for=condition=Ready certificate/openbao-tls --timeout=5m
kubectl get pods -n tools -l app.kubernetes.io/name=openbao
```

The static-key secret is mounted read-only at `/openbao/secrets`; [`values.yaml`](./values.yaml) points the static seal at `/openbao/secrets/unseal.key`. The `openbao-tls` certificate Secret is used by the Ingress and is not mounted into the OpenBao pod. The chart configuration uses the stable key ID `homelab-static-key-1`. Do not change that ID or generate a new key for an existing OpenBao data store.

For direct troubleshooting access, run:

```bash
kubectl port-forward -n tools service/openbao 8200:8200
```

The liveness probe treats sealed and uninitialized health responses as alive, so OpenBao stays running for bootstrap. Initialize OpenBao **once**, after the pod is running. The API listener uses HTTP inside the cluster, so the loopback bootstrap command also uses HTTP:

```bash
INIT_FILE="$HOME/repositories/k8s-home-secrets/openbao/initialization.json"
if [ -e "$INIT_FILE" ]; then
  echo "Initialization file already exists; do not overwrite it."
  exit 1
fi

umask 077
kubectl exec -n tools openbao-0 -- \
  env BAO_ADDR=http://127.0.0.1:8200 bao operator init -format=json > "$INIT_FILE"
```

The JSON file contains the initial root token and recovery keys. Keep it in the private repository or another secure place; do not add it to this public repository. The root token is used to sign in with the Token method in the UI. Auto-unseal uses the static key after initialization; recovery keys are still needed for certain administrative operations. Do not run `bao operator init` again when restoring an existing instance.

## Username/password login

The `userpass` auth method is enabled with an `admin` user and an `admin` policy for full OpenBao administration. The generated password is stored in `openbao/admin-credentials.json` in the private secrets repository. Use username `admin` and that password with the Username and Password login method in the UI. Keep the root token as a separate break-glass credential. The auth method, user, and policy are stored in OpenBao's data; after a fresh initialization, configure them again.

Run this on your trusted workstation with `bao` and `jq` installed, not inside the OpenBao pod: it reads the private credential files on your workstation and connects to OpenBao through its HTTPS Ingress. To change the admin password, use the root token from the private initialization file. This prompts for the new password without echoing it or placing it in shell history, updates OpenBao, and replaces the saved password in the private credentials file:

```bash
(
set -euo pipefail
export BAO_ADDR="https://openbao.nf.lab"
export BAO_TOKEN="$(jq -r '.root_token' "$HOME/repositories/k8s-home-secrets/openbao/initialization.json")"

CREDENTIALS="$HOME/repositories/k8s-home-secrets/openbao/admin-credentials.json"
umask 077
PASSWORD_FILE="$(mktemp)"
UPDATED_FILE="$(mktemp "$HOME/repositories/k8s-home-secrets/openbao/.admin-credentials.XXXXXX")"
trap 'rm -f "$PASSWORD_FILE" "$UPDATED_FILE"; unset BAO_TOKEN NEW_PASSWORD' EXIT

read -r -s -p "New admin password: " NEW_PASSWORD
printf '\n'
printf '%s' "$NEW_PASSWORD" > "$PASSWORD_FILE"
unset NEW_PASSWORD

bao write auth/userpass/users/admin "password=@$PASSWORD_FILE" policies=admin
jq --rawfile password "$PASSWORD_FILE" '.password = $password' "$CREDENTIALS" > "$UPDATED_FILE"
chmod 600 "$UPDATED_FILE"
mv "$UPDATED_FILE" "$CREDENTIALS"
echo "Admin password updated."
)
```

The CLI must trust the `nf.lab` CA when using the HTTPS address above. The temporary files are removed when the command exits.

Check the seal status:

```bash
kubectl exec -n tools openbao-0 -- \
  env BAO_ADDR=http://127.0.0.1:8200 bao status
```

After saving the key and recovery keys, test a normal restart:

```bash
kubectl delete pod -n tools openbao-0
kubectl wait -n tools --for=condition=Ready pod/openbao-0 --timeout=5m
kubectl exec -n tools openbao-0 -- \
  env BAO_ADDR=http://127.0.0.1:8200 bao status
```

The status should report `Initialized: true` and `Sealed: false`. Clients connect through Traefik at `https://openbao.nf.lab`; they must trust the `nf-lab` CA certificate.

## Back up OpenBao data

The static key is **not** a backup of OpenBao's database. Save Raft snapshots to the private repository regularly. With the OpenBao CLI installed locally and authenticated to the instance:

```bash
export BAO_ADDR="https://openbao.nf.lab"
PRIVATE_REPO="$HOME/repositories/k8s-home-secrets"
SNAPSHOT="$HOME/repositories/k8s-home-secrets/openbao/raft-$(date +%Y%m%d-%H%M%S).snap"

bao operator raft snapshot save "$SNAPSHOT"
git -C "$PRIVATE_REPO" add "openbao/$(basename "$SNAPSHOT")"
git -C "$PRIVATE_REPO" commit -m "Back up OpenBao Raft data"
git -C "$PRIVATE_REPO" push
```

Also retain a Longhorn backup of the OpenBao data volume if you use Longhorn backups. A Raft snapshot or storage-volume backup is needed to recover secrets and configuration; the seal key alone cannot restore them.

## Restore onto a new Kubernetes cluster

The key is only the seal key; it does not contain your OpenBao data. Keep either a Longhorn backup of the `data-openbao-0` volume or a Raft snapshot in the private repository.

1. Rebuild Kubernetes and Longhorn. Restore cert-manager with the `nf-lab` ClusterIssuer and Traefik. Clone the public `k8s-home` repository and private `k8s-home-secrets` repository.
2. Recreate namespace `tools`, the `openbao-static-seal` Secret, and the `openbao-tls` certificate using the commands in **Install and initialize**.
3. Choose how to restore OpenBao's data:
   - **Longhorn volume backup:** restore it as the `data-openbao-0` PVC in namespace `tools` **before** applying the chart. Do not initialize OpenBao; it should read the restored data and auto-unseal with the saved key.
   - **Raft snapshot:** leave the PVC empty and continue. After installing the chart, initialize this fresh instance once, authenticate using its temporary root token, then run `bao operator raft snapshot restore <snapshot-file>`. The restore replaces the temporary instance's data with the snapshot. Afterward, use the original root token and recovery keys from the snapshot.
4. Apply the Helm chart from this directory; it creates the ClusterIP Service and Traefik Ingress. The StatefulSet claim is named `data-openbao-0`.
5. For a Raft snapshot restore, set `BAO_ADDR` and use the temporary root token to restore the saved snapshot:
   ```bash
   export BAO_ADDR="https://openbao.nf.lab"
   bao login
   bao operator raft snapshot restore "$HOME/repositories/k8s-home-secrets/openbao/raft-YYYYMMDD-HHMMSS.snap"
   ```
   `bao login` prompts for the temporary root token. After the restore, use the original root token and recovery keys from the snapshot.
6. Check `bao status`; the restored instance should report `Initialized: true` and `Sealed: false`.

See the [OpenBao Raft snapshot command documentation](https://openbao.org/docs/commands/operator/raft/) for snapshot save and restore details. Do not use `-force` for routine restores; it bypasses checks that the seal keys match the snapshot.

Keep the key, recovery keys, and data backups available independently of the Kubernetes cluster. If the static key is lost, OpenBao cannot decrypt its stored data.

## References

- [OpenBao static seal documentation](https://openbao.org/docs/configuration/seal/static/)
- [OpenBao seal and unseal concepts](https://openbao.org/docs/concepts/seal/)
- [OpenBao Raft snapshot commands](https://openbao.org/docs/commands/operator/raft/)
- [OpenBao Helm chart](https://github.com/openbao/openbao-helm)
