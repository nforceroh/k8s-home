# Repository Guide

## Deployment Ownership

- `virt01/automated/` contains applications managed through GitOps by Argo CD. Make desired-state changes in this repository and follow the app's existing Helm or Kubernetes-manifest structure. Argo CD reconciles these files to the cluster.
- `virt01/manual/` contains applications deployed and maintained manually, outside Argo CD. Follow the instructions and deployment method documented for each app; do not assume Argo CD will apply changes there.
- `virt01/deprecated/` contains retired or superseded app material. Treat it as historical unless a task explicitly targets it.

## Repository Map

- `virt01/argocd/` and `virt01/appsConfigurator/` configure Argo CD and application discovery. Changes here can affect how apps are installed or reconciled.
- `virt01/globalValues.yaml` contains values shared by the virt01 app configuration.
- `ansible-k8s/` contains Ansible roles and dependencies for preparing hosts and installing Kubernetes.
- `ref/` holds operational notes, reference configurations, and supporting scripts.
- `scripts/` contains repository utilities; `updatecli/` contains chart-update automation.
- `README.md` contains workstation setup and operational procedures.

## Working in This Repository

- Before changing an app, inspect its local README, chart or manifests, and a neighboring app with the same deployment style.
- For `virt01/automated/`, change the checked-in desired state rather than making an untracked live-cluster change. Check the relevant Argo CD ApplicationSet when changing app discovery or ownership.
- For `virt01/manual/`, preserve the app's manual deployment workflow and update its documentation when the procedure changes.
- Keep credentials and other secrets in the repository's established secret-management workflow; do not add plaintext credentials.
- Validate with the tools appropriate to the changed files, such as `helm lint` and `helm template` for charts, `kustomize build` for Kustomize apps, or Ansible syntax checks for playbooks and roles. State any checks that could not be run.

## Agent skills

### Issue tracker

Issues are tracked on GitHub. See `docs/agents/issue-tracker.md`.

### Triage labels

Default triage labels are used: needs-triage, needs-info, ready-for-agent, ready-for-human, wontfix. See `docs/agents/triage-labels.md`.

### Domain docs

Single-context layout. See `docs/agents/domain.md`.

### AI Agents

AI agents (KubeOpenCode, Hermes, OpenCode) are deployed in `virt01/manual/ai/`. These are manually managed outside Argo CD.

#### Secret Management

All agent secrets must use sealedsecrets. The workflow is:

1. Create a regular secret in a temp namespace
2. Use `kubeseal` to create a `SealedSecret`
3. Commit the `SealedSecret` to `~/repositories/k8s-home-secrets`
4. Apply with `kubectl apply -f sealedsecret.yaml`

Example for new agents:
```bash
kubectl create secret generic newagent-secrets \
  --namespace=newagent \
  --from-literal=openrouter-api-key=YOUR_OPENROUTER_API_KEY \
  --dry-run=client -o json | \
  kubeseal --format=yaml > ~/repositories/k8s-home-secrets/newagent-sealed-secret.yaml
```

See `virt01/manual/ai/create-secrets.sh` for existing agent secret creation scripts.

## Certificates and DNS

### Certificate issuers

Choose the `ClusterIssuer` based on the hostname:

- Use `nf-lab` for internal `nf.lab` names. It requests certificates from the
  internal ACME service at `https://ca.nf.lab/acme/acme/directory` and uses
  RFC2136 DNS-01 updates against `10.0.0.2`.
- Use `letsencrypt-production` for public `nforcer.com` names. It requests
  production Let's Encrypt certificates and uses Cloudflare DNS-01.

Set `cert-manager.io/cluster-issuer` on an Ingress, or use the same issuer name
with `issuerRef.kind: ClusterIssuer` in a `Certificate`. Issuer definitions
are in `virt01/automated/operators/cert-manager/templates/clusterIssuers.yaml`.

### DNS records

Two ExternalDNS releases watch `Ingress`, `Service`, and ExternalDNS
`DNSEndpoint` resources. Domain filters keep their zone ownership separate:

- `external-dns-pdns` manages `nf.lab`, `k3s.nf.lab`, and `test.nf.lab` through
  PowerDNS at `10.0.0.2:8081`.
- `external-dns-cf` manages `nforcer.com` through Cloudflare.

Both use TXT records for ownership (`txtOwnerId: k8s`, `txtPrefix: txt-`) and
`policy: sync`. Set `external-dns.kubernetes.io/target` on an Ingress when its
record should point to a specific target; for example, internal ingress
records point to `traefik.k3s.nf.lab`, while public ones can point to
`dual.nforcer.com`.

cert-manager uses `10.0.0.1` as its recursive DNS resolver for DNS-01 checks.
The ExternalDNS provider and zone settings are in the corresponding
`virt01/automated/operators/external-dns-*/values.yaml` files.
