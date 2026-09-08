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

All three storage mounts (NFS warm tier, R2 cold tier, and the unified MergerFS pool) are configured through `/etc/fstab`. Systemd's built-in fstab generator automatically creates the equivalent mount units at boot (and on `daemon-reload`), named after the escaped mount path — so `/mnt/nfs_emby` becomes `mnt-nfs_emby.mount` automatically.

> **No systemd unit files to write, enable, or maintain.** The only systemd commands you'll ever run for this setup are `systemctl daemon-reload` (after editing `/etc/fstab`) and `mount -a` (to apply changes without rebooting). `systemctl status`/`journalctl -u` work against the auto-generated unit names if you need to inspect a mount's state.

### A. Local Mount Points Preparation

```bash
sudo mkdir -p /mnt/hdd01/emby /mnt/nfs_emby /mnt/r2_emby /mnt/emby_unified
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
> --endpoint=https://<YOUR_ACCOUNT_ID>.r2.cloudflarestorage.com
> ```

> **`x-systemd.mount-timeout=180`** gives GeeseFS extra time to retry past transient Cloudflare edge hiccups (occasional `s3.WARNING http=522` lines even with a correct endpoint) before systemd kills the mount attempt as timed out. The default timeout (90s) can be too short if several 522 retries happen before the connection succeeds.

> **`x-systemd.requires=`** and **`x-systemd.after=`** on the MergerFS line ensure `mnt-emby_unified` waits for both the NFS and R2 mounts to be up before it mounts itself.

> **`nofail`** on all three lines means the boot won't hang or drop to emergency mode if one storage tier is slow or briefly unavailable at boot time.

### C. Apply and Verify

```bash
sudo systemctl daemon-reload
sudo mount -a
systemctl status mnt-nfs_emby.mount mnt-r2_emby.mount mnt-emby_unified.mount
df -h /mnt/nfs_emby /mnt/r2_emby /mnt/emby_unified
```

> **Note:** an fstab entry doesn't automatically retry itself after a failed mount — `x-systemd.mount-timeout=180` reduces how often a mount fails in the first place (by giving GeeseFS more time to survive transient 522s), but if it does fail you'll need to run `sudo mount -a` again manually or via a retry cron/systemd timer.

## 4. The Nightly Cascade Automation Engine

The tiering logic lives in `cascade_tier.sh`, provided alongside this README. Copy it to `/opt/tiering/cascade_tier.sh` on the host and make it executable:

```bash
sudo mkdir -p /opt/tiering
sudo cp cascade_tier.sh /opt/tiering/cascade_tier.sh
sudo chmod +x /opt/tiering/cascade_tier.sh
```

**Available flags:**

| Flag | Default | Purpose |
|---|---|---|
| `--dry-run` | off | Report what would move, no changes made |
| `--path <subfolder>` | full tree | Scope the scan to a subfolder relative to the HOT/WARM roots — useful for isolated testing |
| `--hot-days <N>` | `30` | Age (in days) after which files move HOT → WARM |
| `--warm-days <N>` | `60` | Age (in days) after which files move WARM → COLD |

> **Dry run:** before letting this touch real files, run it with `--dry-run` to see how many files and how much data would move at each tier, with no `mv`/`mkdir`/delete actually happening:
> ```bash
> sudo /opt/tiering/cascade_tier.sh --dry-run
> ```
> It reports file counts and total size for both the WARM→COLD and HOT→WARM transitions, plus a sample of filenames, so you can sanity-check the numbers before it runs for real (e.g. via cron).
>
> **Adjusting retention periods:** override the defaults per run with `--hot-days` and `--warm-days`, e.g. to keep files on HOT for 14 days and on WARM for 90 days:
> ```bash
> sudo /opt/tiering/cascade_tier.sh --hot-days 14 --warm-days 90
> ```
> If you want a permanent change rather than a one-off override, either bake the flags into the crontab line below, or edit the `HOT_DAYS=30` / `WARM_DAYS=60` defaults directly in the script.

Attach it to your root system crontab (`sudo crontab -e`) to execute automatically every night at 2:00 AM:

```
0 2 * * * /opt/tiering/cascade_tier.sh > /var/log/media_tiering.log 2>&1
```

To run with non-default retention periods on a schedule, just add the flags to the cron line, e.g.:

```
0 2 * * * /opt/tiering/cascade_tier.sh --hot-days 14 --warm-days 90 > /var/log/media_tiering.log 2>&1
```

## 5. Application Configuration (Emby, Radarr, Sonarr)

Emby, Radarr, and Sonarr each need their media volumes pointed at the unified MergerFS mount (`/mnt/emby_unified`) rather than a raw tier path, plus a mount-ordering safeguard and (for Radarr/Sonarr) some download-folder/hardlink considerations. See **`setup_stack.md`** for the full explanation and concrete before/after Kubernetes manifests for all three apps.

## 6. Transfer Speed Testing

Before relying on any tier for live playback, it's worth benchmarking write/read throughput and seek latency — especially for the COLD (R2) tier, since sequential throughput and random-seek performance (scrubbing, resuming playback) are different things and a tier can be fine at one and poor at the other.

`xferspeed.sh` tests any combination of the three tiers using the same methodology: write a test file, clear caches, read it back sequentially, then measure seek-to-first-byte latency at several offsets. Reference bitrates it compares against:

| Content | Typical bitrate | Required throughput |
|---|---|---|
| 1080p H.264 | 8–10 Mbps | ~1.0–1.3 MB/s |
| 1080p remux/high-bitrate | 20–35 Mbps | ~2.5–4.4 MB/s |
| 4K H.265 | 25–40 Mbps | ~3.1–5.0 MB/s |
| 4K remux (UHD Blu-ray) | 60–100+ Mbps | ~7.5–12.5+ MB/s |

**Available flags:**

| Flag | Default | Purpose |
|---|---|---|
| `--tier <hot\|warm\|cold>` | `hot,warm,cold` | Comma-separated list of tiers to test |
| `--size <MB>` | `2048` | Test file size per stream, in MB |
| `--streams <N>` | `1` | Number of concurrent streams to simulate |
| `--keep` | off | Keep test files afterward instead of deleting them |

**Test each tier individually:**

```bash
sudo bash xferspeed.sh --tier hot     # baseline: local ZFS array
sudo bash xferspeed.sh --tier warm    # LAN NFS share
sudo bash xferspeed.sh --tier cold    # R2 via GeeseFS — the one that matters most
```

**Test all three together and compare side-by-side** (default behavior, prints a summary table at the end):

```bash
sudo bash xferspeed.sh
```

**Simulate 3 concurrent 4K streams hitting cold storage at once:**

```bash
sudo bash xferspeed.sh --tier cold --size 4096 --streams 3
```

This reports both aggregate throughput across all 3 simulated streams and the effective per-stream rate, so you can answer "can 3 people watch 4K remuxes off R2 simultaneously?" directly.

**Interpreting results:**

- Compare COLD's numbers against HOT/WARM's, not just against the bitrate table — cold storage will always be slower, the question is whether it's *still fast enough*.
- Sequential throughput and seek latency are independent — a tier can have plenty of bandwidth but still feel laggy on scrubbing/resume if seek times are multiple seconds. Under ~1–2s per seek is generally fine for Emby; 3s+ will be noticeable.
- Run more than once, especially for COLD — R2/network variance (like the transient 522s covered in Troubleshooting below) can make a single run misleading.
- For a true worst-case COLD read, remount the R2 tier (`sudo umount /mnt/r2_emby && sudo mount /mnt/r2_emby`) before testing — GeeseFS keeps some in-memory state beyond its on-disk cache that this script clears.
- Clean up test files afterward is the default; pass `--keep` if you want to re-run reads against the *same* file to isolate read-path variance from write variance.

## 7. Troubleshooting

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