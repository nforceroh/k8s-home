# CONTEXT.md

## Glossary

This file defines the canonical terms for this k8s cluster management repository. Use these terms consistently in issues, ADRs, and code.

### Deployment Strategies

| Term | Definition |
| ---- | ----------
| `argo-cd-deploy` | GitOps deployment via Argo CD applying desired-state manifests from this repo |
| `manual-deploy` | Manual `kubectl apply` or `helm upgrade` outside Argo CD workflow |
| `helm-bump` | Automatic chart dependency version bump via updatecli tooling |

### Cluster Resources

| Term | Definition |
| ---- | ----------
| `k8s-cluster` | The target Kubernetes cluster (k3s/nf.lab production environment) |
| `namespace` | Logical partition for app isolation; conventions: `torrent`, `home-assistant`, `tools` |
| `gvk` | Group-Version-Kind identifier for Kubernetes API objects (e.g., `Deployment/v1`) |

### GitOps & Deployment

| Term | Definition |
| ---- | ----------
| `desired-state` | The checked-in YAML/Helm that Argo CD reconciles to the cluster |
| `drift` | Difference between desired-state and actual cluster state |
| `app-set` | Argo CD ApplicationSet resource managing multiple app deployments |

### Observability

| Term | Definition |
| ---- | ----------
| `sealed-secrets` | Encrypted secrets managed via bitnami/sealed-secrets controller — **upstream source is private GitHub repo** `https://github.com/nforceroh/k8s-home-secrets`; this repo contains manually copied/sealed manifests only |
| `cert-manager` | TLS certificate automation for ingress resources |
| `metrics-server` | Resource metrics collection for HPA and autoscaling |
| `prometheus` | Open-source monitoring system; core scrape + rule engine for this repo's k8s cluster |
| `grafana` | Visualization layer for Prometheus metrics; dashboards for storage, GPU, and infrastructure |
| `exporter` | Prometheus exporter binary that translates k8s/OS metrics into Prometheus format; this repo uses: `zfs-exporter`, `nvidia-dcgm-exporter`, `smartctl-exporter`, `ht802-snmp-exporter`, `idrac-exporter` |
| `dashboard` | Grafana dashboard JSON file; this repo's dashboards reside in `kube-prometheus-stack/dashboards/` and cover: infrastructure (BMC, MB, MetalLB, node-exporter, ZFS, NVIDIA, OpenSense, Redis, sealed-secrets, smartctl, UPS, WiFi, Velero, applications) |
| `scrape-config` | Prometheus configuration for service discovery; this repo uses `additional-scrape-configs.yaml` to extend default scrape targets |
| `alertmanager` | Alert routing and notification management; configured via `alertmanager-config-smtp.yaml` in kube-prometheus-stack |
| `release-cycle` | kube-prometheus-stack charts are updated periodically (current: `86.1.0`); chart-bumping via `updatecli` runs on the 1st of each month |

### Infrastructure

| Term | Definition |
| ---- | ----------
| `mergerFS` | Filesystem pooling multiple drives into single mount |
| `talos` | Linux distro for k8s cluster nodes (controlplane/worker) — **not used** in this repo |
| `pxe` | Pre-boot execution environment for diskless node bootstrapping — **not used** |
| `gpu-node` | Single-node Ubuntu 26.04 server with NVIDIA GPU hardware |
| `gpu-driver` | NVIDIA driver installed via `apt` package manager (e.g., `nvidia-driver-535`) |
| `gpu-operator` | NVIDIA GPU Operator managing GPU resources and driver deployment within the k8s cluster; used for GPU pod scheduling, resource quotas, and runtime configuration. Coexists with apt-installed driver base on single-node Ubuntu 26.04 for compatibility with existing workloads. |
| `cuda-version` | CUDA runtime version compatible with apt-installed driver (managed by apps) |
| `mig-partition` | **Not applicable** — consumer-grade single node, not datacenter GPU |
| `gpu-kernel-modules` | NVIDIA kernel modules loaded by `nvidia-driver` package (auto-installed) |
| `gpu-sysctl` | **Not manually managed** — driver package handles kernel parameters |
| `nvidia-firmware` | Installed via `apt install nvidia-driver` or `nvidia-kernel-common` |

### Development Workflow

| Term | Definition |
| ---- | ----------
| `gitops` | Change-driven deployment via GitOps (Argo CD) — **not for driver updates** |
| `worktree` | Git worktree for isolated feature/fix development |
| `pr-surface` | How pull requests surface for triage (GitHub Issues vs. PRs as requests) |
| `gpu-patch-workflow` | **`apt-update`** | `apt-install` | `dkms-build` | `reboot-trigger` |
| `patch-rollout-strategy` | **Single node: immediate effect** — no rolling update needed |
| `patch-prerequisites` | `driver-version-compatible` | `kernel-headers-available` | `system-reboot-allowed` | `services-restarted` |
| `nvidia-apt-source` | `official-repo` | `graphics-drivers PPA` | `third-party` |
| `storage-tiering` | 3-tier cascading storage with MergerFS/GeeseFS for Emby/media |
| `storage-hot` | Tier 1: Local ZFS (`/mnt/hdd01/emby`) — high IOPS, fast access |
| `storage-warm` | Tier 2: NFS share from OPNsense (`/mnt/nfs_emby`) — LAN retention |
| `storage-cold` | Tier 3: Cloudflare R2 via GeeseFS (`/mnt/r2_emby`) — egress-free archival |
| `storage-unified-mount` | `/mnt/emby_unified` — single virtual pool view for all apps |
| `storage-tier-retention` | HOT→WARM: default 30d; WARM→COLD: default 60d (configurable via `cascade_tier.sh`) |
| `storage-app-integration` | Only Emby, Sonarr, Radarr use `/mnt/emby_unified` as unified media library mount; other apps should use raw tier paths or separate mounts. Apps must point volumes at `/mnt/emby_unified`, NOT raw tier paths like `/mnt/hdd01/emby/Movies` — files that tier-migrate will silently disappear from raw-path mounts. New material added via Sonarr/Radarr/Emby goes to HOT tier (`/mnt/hdd01/emby`); watched/older material ages and cascades to WARM (`/mnt/nfs_emby`) then COLD (`/mnt/r2_emby`) via `cascade_tier.sh`. |
| `storage-cascade-tier-script` | `ref/mergerFS/cascade_tier.sh` — nightly tier migration workflow |
| `storage-throughput-hot` | ~1733 Mbps write, ~5940 Mbps read (local ZFS benchmark) |
| `storage-throughput-warm` | ~955 Mbps write, ~3125 Mbps read (NFS benchmark) |
| `storage-throughput-cold` | ~1050 Mbps write, ~2969 Mbps read (R2/GeeseFS benchmark) |
| `storage-download-staging` | Downloads folder should be on HOT tier, NOT inside tiering pool |
| `chart-bumping` | Automatic Helm dependency version bump via `updatecli` tooling |
| `media-app` | Application for managing media library; this repo uses: `emby`, `sonarr`, `radarr`, `bazarr`, `seerr`, `subarr`, `subgen` |
| `media-unified-mount` | `/mnt/emby_unified` — single MergerFS pool mount that Emby, Sonarr, Radarr, Bazarr, Seerr, Subarr, and Subgen all use as their library volume source |
| `media-hot-tier` | `/mnt/hdd01/emby` — local ZFS tier; new material is written here first by Sonarr/Radarr/Emby |
| `media-warm-tier` | `/mnt/nfs_emby` — NFS share from OPNsense; watched material ages into this tier after 30 days |
| `media-cold-tier` | `/mnt/r2_emby` — Cloudflare R2 via GeeseFS; old/watched material cascades here after 60 days total |
| `media-cascade-script` | `ref/mergerFS/cascade_tier.sh` — nightly tier migration workflow that moves files HOT→WARM→COLD based on age retention |
| `media-app-integration` | **Only Emby, Sonarr, Radarr use `/mnt/emby_unified`** as unified media library mount; other apps (Bazarr, Seerr, Subarr, Subgen) should use raw tier paths or separate mounts per their own configuration |
| `media-download-staging` | Download client completed folder should be on HOT tier local ZFS (`/mnt/hdd01/emby`), NOT inside the tiering pool — this prevents downloaded files from being immediately aged out by `cascade_tier.sh` |
| `media-rescan-workflow` | After any tier migration, run manual library rescan in each app: Emby (Library → Update Library), Sonarr/Radarr (Library → Rescan), Bazarr/Seerr/Subarr/Subgen (scan library folders) to re-verify file health against now-correct paths |
| `updatecli-manifest` | YAML manifest generated by `chart_bumper.py` for `updatecli` CLI |
| `excluded-charts` | Chart dependencies skipped during bump: `gpu-operator` (by design) |
| `bump-major-minor` | `BUMP_MAJOR=true` enables major/minor bumps; default is patch-only |
| `chart-dependency-file` | `Chart.yaml` — source file where dependencies are defined |
| `github-actions-bot` | `github-actions` user email `bots@updatecli.io` for PR authorship |
| `updatecli-schedule` | Runs on the **1st of each month** via GitHub Actions workflow (cron: `0 0 1 * *`) |
| `updatecli-trigger` | Monthly chart dependency review; also triggered manually via `workflow_dispatch` |
| `migrate-pvc-namespace` | `scripts/migrate_pvc_namespace.sh` — migrate PVCs between namespaces |