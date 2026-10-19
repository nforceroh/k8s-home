# OpenBao: pre-provisioning the static-seal Secret, and Raft snapshots to Cloudflare R2

Research note. Applies to the vendored chart at
`virt01/manual/tools/openbao/charts/openbao-0.30.4/openbao` (openbao-helm
`0.30.4`, app version `v2.7.1`) and the deployment procedure in
`virt01/manual/tools/openbao/readme.md`. No cluster changes were made while
researching this; all claims are cited to primary sources (official OpenBao
docs/source, the openbao-helm chart source, and official Cloudflare R2 docs).

## Question 1: Can Sealed Secrets or SOPS provision the static-seal Secret *before* OpenBao starts?

**Short answer: yes, both can, and for the same structural reason** — neither
tool's decryption path depends on a running OpenBao instance. Each has its
own prior bootstrap dependency instead (a controller key or a SOPS
decryption key), which is the actual "chicken-and-egg" root that must be
solved once, out of band.

### Why this works at all

OpenBao's static seal only reads a 32-byte key from a file (or env var) that
must already exist on disk before the OpenBao process starts and unseals:

> "The static key seal configures OpenBao to use static keys provided
> alongside the configuration file as the Auto Unseal mechanism... as a file
> (using the `file://` syntax). This key must be a 32-bytes for use as a
> AES-256-GCM-96 key."
> — [OpenBao static seal docs](https://openbao.org/docs/configuration/seal/static/)

In this repo's chart, that file is supplied by mounting a Kubernetes Secret
(`openbao-static-seal`) at `/openbao/secrets/unseal.key`
(`virt01/manual/tools/openbao/values.yaml:188-200`, referencing
`current_key = "file:///openbao/secrets/unseal.key"` at
`virt01/manual/tools/openbao/values.yaml:55-57`). Kubernetes only needs that
Secret object to exist before the Pod is scheduled — it has no awareness of,
or dependency on, OpenBao itself. The current documented procedure creates
it manually with `kubectl create secret generic openbao-static-seal
--from-file=unseal.key=...` (`virt01/manual/tools/openbao/readme.md`, "Install
and initialize" section). That manual step is exactly what Sealed Secrets or
SOPS would replace.

### Sealed Secrets

Sealed Secrets decrypts independently of OpenBao, via its own controller and
keypair:

> "Encrypt your Secret into a SealedSecret, which *is* safe to store - even
> inside a public repository. The SealedSecret can be decrypted only by the
> controller running in the target cluster and nobody else..."
> — [bitnami-labs/sealed-secrets README](https://github.com/bitnami-labs/sealed-secrets/blob/main/README.md)

Mechanically: a `SealedSecret` custom resource is committed to Git/applied to
the cluster, the in-cluster `sealed-secrets-controller` decrypts it with its
own private key and writes out a plain `v1/Secret`. This path has **no
dependency on OpenBao being up, initialized, or unsealed** — the only
prerequisite is that the sealed-secrets controller (and its keypair) already
exists in the cluster, which this repo already has running (see
`virt01/automated/sealed-secrets/readme.md` and the existing
`kubeseal`-based workflow documented in `AGENTS.md`, "Secret Management").
Sealing the static key with `kubeseal` and committing the resulting
`SealedSecret` would produce the `openbao-static-seal` Secret automatically
on sync, before the OpenBao StatefulSet pod is created — satisfying the
"before OpenBao starts" requirement.

Caveat: the static key is explicitly treated in this repo as **not** to be
committed to the public `k8s-home` repository (`virt01/manual/tools/openbao/readme.md`,
"What must be backed up"). A `SealedSecret` is safe to commit to a public
repo only in the sense that it cannot be reversed to the plaintext *without*
the controller's private key — the project's own docs call this out
generally ("SealedSecret can be decrypted only by the controller... and
nobody else... is able to obtain the original Secret"), so adopting this
path would be a deliberate change from the current "keep the raw key out of
Git entirely" policy to "keep it in Git only in sealed form," not something
verified against this repo's threat model here.

### SOPS

SOPS itself is a file encryption/decryption tool, not a Kubernetes
controller:

> "SOPS is an editor of encrypted files that supports YAML, JSON, ENV, INI
> and BINARY formats and encrypts with AWS KMS, GCP KMS, Azure Key Vault,
> HuaweiCloud KMS, age, and PGP."
> — [getsops/sops README](https://github.com/getsops/sops/blob/main/README.rst)

Decryption requires only the matching PGP/age/KMS private key, independent
of OpenBao. The most common cluster-integrated pattern (Flux's
`kustomize-controller` SOPS support) makes this explicit:

> "Create a Kubernetes secret named `sops-gpg` in the `flux-system`
> namespace [containing the GPG private key]... `flux create kustomization
> my-secrets ... --decryption-provider=sops --decryption-secret=sops-gpg`"
> — [Flux: Manage Kubernetes secrets with SOPS](https://fluxcd.io/flux/guides/mozilla-sops/)

The decrypting controller (`kustomize-controller`, or equivalently an
Argo CD plugin such as `ksops`/`argocd-vault-plugin` if adopted) reads its
own pre-provisioned decryption key from a Secret/file and writes out the
plain `openbao-static-seal` Secret during reconciliation — again with no
dependency on OpenBao being reachable. This repo uses Argo CD, not Flux
(`AGENTS.md`, "Deployment Ownership"); Argo CD has no built-in SOPS
decryption (unverified beyond the absence of any such feature in Argo CD's
own docs reviewed here), so adopting SOPS would require either a config
management plugin (e.g. `ksops`) or an init/pre-sync step that runs `sops
--decrypt` before `kubectl apply`. Either way, the SOPS key itself (the
"root of trust") still has to be bootstrapped into the cluster or CI runner
once, by hand or via another mechanism — structurally the same bootstrap
problem as Sealed Secrets' controller keypair, just moved one level down.

### Bottom line for Question 1

Both tools can produce the `openbao-static-seal` Secret before the OpenBao
pod starts, because both decrypt using key material that is entirely
independent of OpenBao. Neither tool is verified in this research to require
OpenBao to be running, initialized, or unsealed. The dependency that *does*
exist is each tool's own decryption key (sealed-secrets controller keypair,
already present in this cluster per `virt01/automated/sealed-secrets/`; or a
SOPS PGP/age/KMS key, not currently used in this repo) must be provisioned
beforehand — a one-time manual/out-of-band bootstrap step in both cases,
just as the static seal key itself is today.

## Question 2: Can OpenBao / the official openbao-helm chart export integrated Raft snapshots to Cloudflare R2 via its S3-compatible API?

**Short answer: yes, but only through the chart's external CronJob
snapshot-agent mechanism — not a native/built-in OpenBao feature.**

### OpenBao has no native automated-snapshot feature

OpenBao's own docs state this plainly:

> "There is currently no built-in support for automated snapshots. However,
> OpenBao snapshots can be automated in various ways such as using a cron
> job. We maintain [a repository] containing a collection of external tools
> and instructions for automating snapshots... for Kubernetes we provide a
> container image and CronJob resource. The Kubernetes CronJob can also be
> configured and deployed via the OpenBao Helm chart."
> — [OpenBao: Storage concepts — Backups](https://openbao.org/docs/concepts/storage/)

The only native primitive is the manual/on-demand Raft snapshot command,
which reads/writes a single snapshot file via the OpenBao API/CLI and has no
S3 or cloud-storage concept at all:

> "`snapshot` — Restores and saves snapshots from the Raft cluster"
> — [OpenBao: `bao operator raft` command docs](https://openbao.org/docs/commands/operator/raft/)

This matches how this repo's own `virt01/manual/tools/openbao/readme.md`
documents backups today: `bao operator raft snapshot save <file>` followed
by manually committing the file to the private `k8s-home-secrets` repo —
i.e., no S3/R2 integration is exercised by OpenBao itself.

### The chart's snapshot-agent CronJob is an external, S3-only mechanism

The official openbao-helm chart (vendored at
`virt01/manual/tools/openbao/charts/openbao-0.30.4/openbao`) ships an
optional `snapshotAgent` feature (disabled by default:
`snapshotAgent.enabled: false`,
`virt01/manual/tools/openbao/charts/openbao-0.30.4/openbao/values.yaml:1538-1540`)
that renders a `CronJob`
(`.../templates/snapshotagent-cronjob.yaml`) and a `ConfigMap`
(`.../templates/snapshotagent-configmap.yaml`) wiring S3 parameters as env
vars (`S3_HOST`, `S3_BUCKET`, `S3_URI`, `S3_EXPIRE_DAYS`, `S3CMD_EXTRA_FLAG`)
plus `AWS_ACCESS_KEY_ID`/`AWS_SECRET_ACCESS_KEY` sourced from a named
Secret (`snapshotAgent.s3CredentialsSecret`) — confirmed directly in the
vendored chart source:
`virt01/manual/tools/openbao/charts/openbao-0.30.4/openbao/templates/snapshotagent-configmap.yaml`
and
`virt01/manual/tools/openbao/charts/openbao-0.30.4/openbao/templates/snapshotagent-cronjob.yaml`.
Default image is `ghcr.io/openbao/openbao-snapshot-agent:0.4.5`
(`.../values.yaml:1567-1570`).

OpenBao's own docs confirm this is the officially supported path and show
the exact same generic `s3Host`/`s3Bucket`/`s3Uri` values keys:

> "The below `values.yaml` can be used to set up the Snapshot CronJob with
> OpenBao... `s3CredentialsSecret: "my-s3-credentials"`, `s3Host:
> "s3.eu-east-1.amazonaws.com"`, `s3Bucket: "openbao-snapshots"`, `s3Uri:
> "s3://openbao-snapshots"`... **This feature is available starting with
> OpenBao Helm Chart Version 0.22.0.**"
> — [OpenBao: Helm chart snapshot CronJob example](https://openbao.org/docs/platform/k8s/helm/examples/snapshot-cronjob/)

The CronJob script itself (`openbao/openbao-snapshot-agent`,
`kubernetes/bao-snapshot.sh`) does exactly two things relevant to S3/R2:

```sh
# Create snapshot
bao operator raft snapshot save /bao-snapshots/bao_"$(date +%F-%H%M)".snapshot

# Upload to S3
s3cmd put --recursive /bao-snapshots/ "${S3_URI}" --host="${S3_HOST}" --host-bucket="${S3_BUCKET}" ${S3CMD_EXTRA_FLAG:+$S3CMD_EXTRA_FLAG}
```
— [openbao/openbao-snapshot-agent: `kubernetes/bao-snapshot.sh`](https://github.com/openbao/openbao-snapshot-agent/blob/main/kubernetes/bao-snapshot.sh)

It calls the native `bao operator raft snapshot save` command (same API as
Question 2's "native" primitive above) to produce the file locally, then
shells out to `s3cmd put`/`ls`/`del` against whatever host is given in
`S3_HOST`/`S3_URI`/`S3_BUCKET` — a generic, endpoint-configurable S3 client,
not an AWS-specific one. Authentication docs for the Kubernetes CronJob
confirm `AWS_ACCESS_KEY_ID`/`AWS_SECRET_ACCESS_KEY` are the only credentials
needed, sourced either directly from a Secret or indirectly fetched from
OpenBao via `BAO_SECRET_PATH`:
[openbao-snapshot-agent: `docs/k8s-configuration.md`](https://github.com/openbao/openbao-snapshot-agent/blob/main/docs/k8s-configuration.md).

### Cloudflare R2 side: S3-compatible endpoint and credentials needed

Cloudflare R2 exposes a standard S3-compatible endpoint and the exact
operations the snapshot-agent script needs (object PUT/LIST/DELETE):

> "The API is available via the `https://<ACCOUNT_ID>.r2.cloudflarestorage.com`
> endpoint."
> — [Cloudflare R2: S3 API compatibility](https://developers.cloudflare.com/r2/api/s3/api/)

> "You will also need to configure the `endpoint` in your S3 client to
> `https://<ACCOUNT_ID>.r2.cloudflarestorage.com`... review your **Secret
> Access Key** and **Access Key ID** values. These may often be referred to
> as Client Secret and Client ID, respectively."
> — [Cloudflare R2: Authentication (API tokens)](https://developers.cloudflare.com/r2/api/tokens/)

R2's S3-compatibility page lists `PutObject`, `GetObject`,
`ListObjectsV2`/`ListObjects`, `DeleteObject`, and multipart-upload
operations as implemented (✅) — the baseline operations `s3cmd put`, `ls`,
and `del` rely on — per the same
[S3 API compatibility](https://developers.cloudflare.com/r2/api/s3/api/)
page. Cloudflare's own tooling examples (`boto3`, `rclone`) confirm the
pattern of pointing any generic S3-compatible client at this endpoint with
an R2 API token's access key/secret pair:
[Cloudflare R2: boto3 example](https://developers.cloudflare.com/r2/examples/aws/boto3/).

### What is and isn't verified here

- **Verified**: OpenBao has no native snapshot-to-cloud-storage feature
  (primary source: openbao.org/docs/concepts/storage/). The chart's
  `snapshotAgent` CronJob is the officially documented mechanism for
  automating this, and is generic-S3 rather than AWS-specific
  (`S3_HOST`/`--host` flag, not a hardcoded AWS endpoint).
- **Verified**: R2 offers an S3-compatible endpoint and access-key/secret
  credentials, and implements the basic object PUT/GET/LIST/DELETE
  operations the snapshot script issues.
- **Not verified / not found in either project's docs**: neither OpenBao's,
  openbao-helm's, nor Cloudflare's documentation names this
  `openbao-snapshot-agent` + `s3cmd` + R2 combination explicitly. `s3cmd`'s
  `--host`/`--host-bucket` flags control virtual-host vs. path-style
  addressing, and R2's own docs/examples (boto3, rclone) don't mention
  `s3cmd` by name — getting the bucket-addressing style right for R2 with
  `s3cmd` specifically would need to be validated against a real R2 bucket
  before relying on it, rather than assumed from the chart defaults (which
  show an AWS endpoint, `s3.eu-east-1.amazonaws.com`, as the example value).
- **Out of scope / not investigated**: whether this repo's existing R2
  usage for Emby tiered storage (referenced in
  `docs/adr/0001-unified-media-mount.md`) already has working R2
  credentials/endpoint conventions that could be reused for an OpenBao
  snapshot bucket — this note only verified the OpenBao/chart/R2 mechanism
  in the abstract, not this repo's existing R2 credential layout.

### Bottom line for Question 2

OpenBao itself cannot export Raft snapshots to R2 (or any S3 target) — this
is purely the Helm chart's optional `snapshotAgent` CronJob calling `bao
operator raft snapshot save` and then an `s3cmd` upload to a
generically-configured S3 endpoint. Nothing about that CronJob is AWS-
specific, and R2's S3-compatible endpoint plus API token (access key/secret)
satisfy the credentials/endpoint shape it expects (`S3_HOST` =
`<ACCOUNT_ID>.r2.cloudflarestorage.com`, `AWS_ACCESS_KEY_ID`/
`AWS_SECRET_ACCESS_KEY` = R2 API token key pair). This has not been tested
against a live R2 bucket as part of this research.

## Sources

- OpenBao static seal: https://openbao.org/docs/configuration/seal/static/
- OpenBao `operator raft` commands: https://openbao.org/docs/commands/operator/raft/
- OpenBao storage/backups concepts: https://openbao.org/docs/concepts/storage/
- OpenBao Helm chart snapshot CronJob example: https://openbao.org/docs/platform/k8s/helm/examples/snapshot-cronjob/
- openbao-helm chart README (v0.30.4): https://github.com/openbao/openbao-helm/blob/main/charts/openbao/README.md
- openbao-snapshot-agent README: https://github.com/openbao/openbao-snapshot-agent/blob/main/README.md
- openbao-snapshot-agent Kubernetes config docs: https://github.com/openbao/openbao-snapshot-agent/blob/main/docs/k8s-configuration.md
- openbao-snapshot-agent CronJob script: https://github.com/openbao/openbao-snapshot-agent/blob/main/kubernetes/bao-snapshot.sh
- Sealed Secrets README: https://github.com/bitnami-labs/sealed-secrets/blob/main/README.md
- SOPS README: https://github.com/getsops/sops/blob/main/README.rst
- Flux SOPS guide (reference pattern for in-cluster SOPS decryption): https://fluxcd.io/flux/guides/mozilla-sops/
- Cloudflare R2 S3 API compatibility: https://developers.cloudflare.com/r2/api/s3/api/
- Cloudflare R2 authentication (API tokens / endpoint): https://developers.cloudflare.com/r2/api/tokens/
- Cloudflare R2 boto3 example: https://developers.cloudflare.com/r2/examples/aws/boto3/
- This repo:
  - `virt01/manual/tools/openbao/readme.md`
  - `virt01/manual/tools/openbao/values.yaml`
  - `virt01/manual/tools/openbao/charts/openbao-0.30.4/openbao/values.yaml`
  - `virt01/manual/tools/openbao/charts/openbao-0.30.4/openbao/templates/snapshotagent-configmap.yaml`
  - `virt01/manual/tools/openbao/charts/openbao-0.30.4/openbao/templates/snapshotagent-cronjob.yaml`
  - `virt01/automated/sealed-secrets/readme.md`
  - `AGENTS.md` ("Secret Management", "Deployment Ownership")
  - `docs/adr/0001-unified-media-mount.md` (existing repo use of Cloudflare R2, noted but not re-verified here)
