# 3-Tier Cascading Media Storage for Emby on Kubernetes

A resilient, low-cost tiered storage engine built for single-node Kubernetes clusters running on Ubuntu. This architecture unifies fast local storage, a large remote network pool, and egress-free cloud object storage into a single virtual path using MergerFS and GeeseFS.

## Architecture Overview

```
                        ┌───────────────────┐
                        │   Emby K8s Pod    │
                        └─────────┬─────────┘
                                  │ (Sees single /data mount)
                        ┌─────────▼─────────┐
                        │ /mnt/emby_unified │ (MergerFS Virtual Pool)
                        └────┬────┬────┬────┘
                             │    │    │
       ┌─────────────────────┘    │    └──────────────────────┐
       │ (0-30 Days: Hot)         │ (31-60 Days: Warm)        │ (61+ Days: Cold)
┌──────▼──────────┐      ┌────────▼─────────┐      ┌──────────▼─────────┐
│ /mnt/hdd01/emby │      │  /mnt/nfs_emby   │      │    /mnt/r2_emby    │
└─────────────────┘      └────────┬─────────┘      └──────────┬─────────┘
   (Local ZFS)                    │ (LAN NFS)                 │ (GeeseFS FUSE wrapper)
                         ┌────────▼─────────┐      ┌──────────▼─────────┐
                         │   OPNsense FW    │      │   Cloudflare R2    │
                         │   (21TB Pool)    │      │  (Egress-Free S3)  │
                         └───────────────────┘      └────────────────────┘
```

- **Tier 1 (Hot)**: Local ZFS array (`/mnt/hdd01/emby`). Handles newly added media for high IOPS streaming and fast thumbnail generation.
- **Tier 2 (Warm)**: Remote NFS share exported from an OPNsense FreeBSD firewall pool (`/mnt/nfs_emby`). Retains mid-aged data locally on the LAN.
- **Tier 3 (Cold)**: Cloudflare R2 bucket (`/mnt/r2_emby`) mounted via GeeseFS. Stores old, watched data with zero egress fees.

## Prerequisites

On your main Ubuntu node, make sure you have the required filesystem packages installed:

```bash
sudo apt update
sudo apt install fuse3 mergerfs nfs-common wget -y
```

> For `fuse.mergerfs` and `fuse.geesefs` entries in `/etc/fstab` to work, the `mergerfs` and `geesefs` binaries just need to be on `PATH` (e.g. `/usr/bin/mergerfs`, `/usr/local/bin/geesefs`) — `mount(8)` invokes them directly by matching the `fuse.<name>` type to a binary named `<name>`. No separate `mount.fuse` helper package is required for this style of entry.

## 1. Remote Tier Setup (OPNsense / FreeBSD)

Run these commands on your OPNsense shell (`10.0.0.1`) to create the dataset and share it with your Ubuntu subnet (`10.0.0.0/24`):

```bash
# Create the dataset
zfs create k8s-pool/emby

# Export via NFS directly using ZFS attributes
zfs set sharenfs="-alldirs -maproot=root -network=10.0.0.0" k8s-pool/emby

# Reload the mount configuration daemon
service mountd reload
```

## 2. Cloud Tier Setup (GeeseFS & Cloudflare R2)

### A. Download the Binary

Download and register the matching production build of GeeseFS:

```bash
wget https://github.com/yandex-cloud/geesefs/releases/latest/download/geesefs-linux-amd64
chmod +x geesefs-linux-amd64
sudo mv geesefs-linux-amd64 /usr/local/bin/geesefs
```

> **Note:** confirm this matches your CPU architecture (`amd64` vs `arm64`) and check the [GeeseFS releases page](https://github.com/yandex-cloud/geesefs/releases) for the current binary name if this URL changes.

### B. Store R2 Configuration API Secrets

Create a dedicated credentials profile file at `/root/.r2/emby_credentials`:

```ini
[default]
aws_access_key_id = YOUR_CLOUDFLARE_R2_ACCESS_KEY_ID
aws_secret_access_key = YOUR_CLOUDFLARE_R2_SECRET_ACCESS_KEY
```

## 3. Host Mount Configuration via /etc/fstab

Rather than hand-writing systemd `.mount`/`.service` units, this configuration uses `/etc/fstab`. Systemd auto-generates mount units from fstab entries at boot (and on `daemon-reload`), naming each unit after the escaped mount path — so `/mnt/nfs_emby` automatically becomes `mnt-nfs_emby.mount`, with no manual unit files to keep in sync.

### A. Local Mount Points Preparation

```bash
sudo mkdir -p /mnt/zfs_hot /mnt/nfs_emby /mnt/r2_emby /mnt/emby_unified
sudo chmod 777 /mnt/emby_unified
```

### B. Add Entries to /etc/fstab

Edit `/etc/fstab` and add these three lines:

```fstab
# --- Tier 2: OPNsense Warm Storage (NFS) ---
10.0.0.1:/k8s-pool/emby  /mnt/nfs_emby  nfs  defaults,soft,bg,timeo=50,retrans=2,_netdev,nofail  0  0

# --- Tier 3: Cloudflare R2 Cold Storage (GeeseFS) ---
emby  /mnt/r2_emby  fuse.geesefs  _netdev,allow_other,--cache=/tmp/cache,--shared-config=/root/.r2/emby_credentials,--list-type=2,--region=auto,--endpoint=https://YOUR_ACCOUNT_ID.r2.cloudflarestorage.com,x-systemd.mount-timeout=180,nofail  0  0

# --- Unified MergerFS Pool ---
/mnt/hdd01/emby:/mnt/nfs_emby:/mnt/r2_emby  /mnt/emby_unified  fuse.mergerfs  defaults,allow_other,use_ino,category.create=epmfs,moveonenospc=true,func.getattr=newest,x-systemd.requires=mnt-nfs_emby.mount,x-systemd.requires=mnt-r2_emby.mount,x-systemd.after=mnt-nfs_emby.mount,x-systemd.after=mnt-r2_emby.mount,nofail  0  0
```

> **Important:** `emby` in the GeeseFS line is the bucket name (first field), and `--endpoint` must be your **account-specific** R2 endpoint — not the bare `cloudflarestorage.com` domain. The bare domain returns an HTTP 522 (Cloudflare edge timeout, no valid origin) and the mount will never come up. Find your Account ID under **Cloudflare Dashboard → R2 → Overview**, e.g.:
> ```
> --endpoint=https://c8447e01e7c0018cf456923099f43457.r2.cloudflarestorage.com
> ```

> **`x-systemd.mount-timeout=180`** gives GeeseFS extra time to retry past transient Cloudflare edge hiccups (occasional `s3.WARNING http=522` lines even with a correct endpoint) before systemd kills the mount attempt as timed out. The default timeout (90s) can be too short if several 522 retries happen before the connection succeeds.

> **`x-systemd.requires=`** and **`x-systemd.after=`** on the MergerFS line reproduce the dependency ordering that a hand-written unit would need (`mnt-emby_unified` must wait for both the NFS and R2 mounts) — but targeting the auto-generated unit names, so there's no risk of a unit-filename/path mismatch like you'd get writing `.mount` files by hand.

> **`nofail`** on all three lines means the boot won't hang or drop to emergency mode if one storage tier is slow or briefly unavailable at boot time.

### C. Apply and Verify

```bash
sudo systemctl daemon-reload
sudo mount -a
systemctl status mnt-nfs_emby.mount mnt-r2_emby.mount mnt-emby_unified.mount
df -h /mnt/nfs_emby /mnt/r2_emby /mnt/emby_unified
```

> **Trade-off vs. a hand-written systemd `.service`:** a plain fstab entry doesn't automatically retry itself after a failed mount the way a unit with `Restart=on-failure` would — `x-systemd.mount-timeout=180` reduces how often a mount fails in the first place (by giving GeeseFS more time to survive transient 522s), but if it does fail you'll need to `sudo mount -a` again manually or via a retry cron/systemd timer.

## 4. The Nightly Cascade Automation Engine

Create the offloading scheduler file at `/opt/tiering/cascade_tier.sh`:

```bash
#!/bin/bash
#
# Nightly cascade tiering for Emby media.
# Usage:
#   ./cascade_tier.sh            # actually move files
#   ./cascade_tier.sh --dry-run  # report what WOULD move, no changes made

set -uo pipefail

DRY_RUN=false
if [[ "${1:-}" == "--dry-run" ]]; then
    DRY_RUN=true
fi

# Define absolute paths
HOT="/mnt/hdd01/emby"
WARM="/mnt/nfs_emby"
COLD="/mnt/r2_emby"

# Safety Check: Prevent data loops if mounts dropped
if ! mountpoint -q "$WARM" || ! mountpoint -q "$COLD"; then
    echo "Error: One of the remote storage tiers is unmounted. Aborting lifecycle." >&2
    exit 1
fi

sum_bytes() {
    local total=0 f sz
    while IFS= read -r f; do
        [[ -f "$f" ]] || continue
        sz=$(stat -c '%s' "$f" 2>/dev/null || echo 0)
        total=$((total + sz))
    done
    echo "$total"
}

human() {
    numfmt --to=iec-i --suffix=B "$1" 2>/dev/null || echo "${1} bytes"
}

mapfile -t warm_to_cold < <(find "$WARM" -type f -mtime +60)
mapfile -t hot_to_warm  < <(find "$HOT"  -type f -mtime +30)

if $DRY_RUN; then
    warm_bytes=$(printf '%s\n' "${warm_to_cold[@]}" | sum_bytes)
    hot_bytes=$(printf '%s\n' "${hot_to_warm[@]}" | sum_bytes)
    echo "WARM -> COLD: ${#warm_to_cold[@]} files, $(human "$warm_bytes")"
    echo "HOT  -> WARM: ${#hot_to_warm[@]} files, $(human "$hot_bytes")"
    echo "Dry run complete. No files were moved."
    exit 0
fi

# Step A: Move files older than 60 days from WARM (NFS) to COLD (R2 Cloud)
for file in "${warm_to_cold[@]}"; do
    relative_path="${file#$WARM/}"
    relative_dir=$(dirname "$relative_path")
    mkdir -p "$COLD/$relative_dir"
    mv "$file" "$COLD/$relative_path"
done

# Step B: Move files older than 30 days from HOT (Local ZFS) to WARM (NFS)
for file in "${hot_to_warm[@]}"; do
    relative_path="${file#$HOT/}"
    relative_dir=$(dirname "$relative_path")
    mkdir -p "$WARM/$relative_path"
    mv "$file" "$WARM/$relative_path"
done

# Step C: Purge stale empty folders across systems
find "$HOT" -type d -empty -delete 2>/dev/null
find "$WARM" -type d -empty -delete 2>/dev/null
```

> Note: this is a condensed version for readability. The full script (with a per-tier filename sample in dry-run output) is available as `cascade_tier.sh` alongside this README.

> **Note:** the original snippet had `COLD="/mnt/r2_by"`, which doesn't match the `/mnt/r2_emby` mount point used everywhere else — corrected above to `/mnt/r2_emby`.

> **Dry run:** before letting this touch real files, run it with `--dry-run` to see how many files and how much data would move at each tier, with no `mv`/`mkdir`/delete actually happening:
> ```bash
> sudo /opt/tiering/cascade_tier.sh --dry-run
> ```
> It reports file counts and total size for both the WARM→COLD and HOT→WARM transitions, plus a sample of filenames, so you can sanity-check the numbers before it runs for real (e.g. via cron).

Make it executable and attach it to your root system crontab (`sudo crontab -e`) to execute automatically every night at 2:00 AM:

```
0 2 * * * /opt/tiering/cascade_tier.sh > /var/log/media_tiering.log 2>&1
```

## 5. Kubernetes Integration

Map the unified host mount point safely straight into your Emby deployment manifest using standard persistent volume routing maps.

`emby-storage.yaml`:

```yaml
apiVersion: v1
kind: PersistentVolume
metadata:
  name: emby-unified-pv
spec:
  capacity:
    storage: 30Ti
  volumeMode: Filesystem
  accessModes:
    - ReadWriteMany
  persistentVolumeReclaimPolicy: Retain
  storageClassName: manual
  local:
    path: /mnt/emby_unified
  nodeAffinity:
    required:
      nodeSelectorTerms:
        - matchExpressions:
            - key: kubernetes.io/hostname
              operator: In
              values:
                - virt01 # Replace with your exact k8s node hostname
---
apiVersion: v1
kind: PersistentVolumeClaim
metadata:
  name: emby-unified-pvc
spec:
  accessModes:
    - ReadWriteMany
  volumeName: emby-unified-pv
  storageClassName: manual
  resources:
    requests:
      storage: 30Ti
```

Simply update your Emby application deployment pod specification to point its media disk path to use the `emby-unified-pvc` declaration.

## 6. Troubleshooting

**A previous migration used hand-written systemd `.mount`/`.service` units**
If you're moving from that approach to the fstab-based setup in Section 3, make sure the old unit files are fully removed first — a leftover `/etc/systemd/system/mnt-nfs_emby.mount`, `geesefs-r2.service`, or `mnt-emby_unified.mount` will conflict with the units systemd auto-generates from fstab:
```bash
sudo systemctl stop mnt-emby_unified.mount geesefs-r2.service mnt-nfs_emby.mount
sudo systemctl disable mnt-emby_unified.mount geesefs-r2.service mnt-nfs_emby.mount
sudo rm /etc/systemd/system/mnt-emby_unified.mount \
        /etc/systemd/system/geesefs-r2.service \
        /etc/systemd/system/mnt-nfs_emby.mount
sudo systemctl daemon-reload
```

**"Unit `mnt-*.mount` has a bad unit file setting" (only relevant if still using hand-written units)**
The unit filename must exactly match the systemd-escaped `Where=` path. If you rename a mount point (e.g. `/mnt/nfs_warm` → `/mnt/nfs_emby`), you must rename the `.mount` file itself — editing `Where=` alone is not enough. This class of error goes away entirely with the fstab approach, since systemd derives the unit name from the fstab mount point automatically. Confirm naming with:
```bash
systemd-escape -u --path mnt-nfs_emby.mount   # should print /mnt/nfs_emby
```

**"Dependency job for mnt-emby_unified.mount failed"**
This means one of the units it depends on (from `x-systemd.requires=` in the MergerFS fstab line) didn't start. Check each dependency individually:
```bash
systemctl status mnt-nfs_emby.mount mnt-r2_emby.mount
```

**GeeseFS logs `s3.WARNING http=522` repeatedly, then times out**
An HTTP 522 is a Cloudflare edge error meaning the request reached Cloudflare but found no valid origin — this almost always means the `--endpoint` value is wrong. Double-check:
- You're using your account-specific endpoint (`https://<ACCOUNT_ID>.r2.cloudflarestorage.com`), not the bare `cloudflarestorage.com` domain.
- The bucket name (first field of the fstab line) matches your real R2 bucket.
- `/root/.r2/emby_credentials` exists and has valid R2 API tokens.
- The fstab line's comma-separated options have no stray spaces (unlike a systemd unit, fstab options are one continuous comma-separated field — don't split it across lines).

**Mount eventually succeeds but shows as failed / times out on boot**
This means the endpoint and credentials are correct, but a handful of transient 522s from Cloudflare's edge are pushing the connection past the mount timeout. Increase `x-systemd.mount-timeout` in the fstab line (180s is usually enough; try 240–300 if 522s are frequent), then:
```bash
sudo systemctl daemon-reload
sudo mount -a
```
If 522s persist heavily even with a longer timeout, it's worth checking whether anything on your network path (proxy, firewall, DNS) is interfering with the connection to Cloudflare, since occasional edge errors are normal but frequent ones are not.

**Validate an fstab entry before rebooting**
```bash
sudo mount -a --fake --verbose   # dry-run parse of /etc/fstab, doesn't actually mount
findmnt --verify                 # sanity-checks all fstab entries
```