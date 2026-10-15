# ADR-0001: Use Unified Media Mount (/mnt/emby_unified) for Emby, Sonarr, Radarr

## Status
Proposed

## Context

This k8s home server uses a 3-tier cascading storage architecture with MergerFS and GeeseFS for Emby media library management:

- **Tier 1 (HOT)**: Local ZFS (`/mnt/hdd01/emby`) — high IOPS, fast access for new material
- **Tier 2 (WARM)**: NFS from OPNsense (`/mnt/nfs_emby`) — LAN retention for mid-aged data
- **Tier 3 (COLD)**: Cloudflare R2 via GeeseFS (`/mnt/r2_emby`) — egress-free archival for old data

The `cascade_tier.sh` script physically relocates files between tiers as they age (default: 30d HOT→WARM, 60d WARM→COLD).

## Decision

**All Emby, Sonarr, and Radarr containers must mount their media volumes at `/mnt/emby_unified`**, the MergerFS unified pool mount, rather than at raw tier paths (`/mnt/hdd01/emby/Movies`, etc.).

### Why this decision:

1. **Files disappear from raw-path mounts when they tier-migrate**: If a container mounts at `/mnt/hdd01/emby/Movies` and a file ages to WARM/COLD, it moves to `/mnt/nfs_emby/Movies` or `/mnt/r2_emby/Movies` — the container no longer sees it. Only the unified mount transparently resolves to whichever tier the file currently resides on.

2. **Single source of truth**: All three apps (Emby, Sonarr, Radarr) point at the same path, ensuring consistent library views and avoiding duplicate file copies across tiers.

3. **Simplifies app configuration**: Rather than each app managing its own path logic, the node-side `hostPath` volume points at `/mnt/emby_unified`, and each app's container `mountPath` stays the same (e.g., `/movies`, `/tv`).

4. **Future-proof**: If tier architecture changes (e.g., add Tier 4, switch cloud providers), app configurations don't need rewriting — only the node-side mount layout changes.

## Alternatives Considered

| Alternative | Pros | Cons |
| --------- | ---- | ---- |
| **Raw tier paths** (e.g., `/mnt/hdd01/emby/Movies`) | Simpler initial setup; no unified mount needed | Files silently disappear when they tier-migrate; apps lose visibility of watched/archived content; requires per-app tier-awareness |
| **Separate mount per tier** | Explicit tier awareness | Triple the volume definitions; apps need 3x mount configs; operational overhead; still risk of path drift |
| **Unified mount (`/mnt/emby_unified`)** — **CHOSEN** | Transparent tier resolution; single volume definition per app; future-proof; recommended by MergerFS/GeeseFS docs | Requires initial setup of MergerFS pool; minor operational overhead to maintain mount |

## Consequences

### Positive

- Emby, Sonarr, and Radarr always see complete library contents regardless of tier state
- No need to reconfigure apps when files cascade between tiers
- Simplifies backup strategy (single unified path to back up)
- Aligns with MergerFS/GeeseFS recommended pattern

### Negative

- Requires initial configuration change for any existing deployments using raw tier paths
- `initContainer` recommended to guard against mount-ordering race conditions after reboot (see ADR-FORMAT.md pattern)
- Slightly more complex node-side volume setup (but one-time effort)

## Implementation

### For New Deployments

```yaml
 volumes:
   - name: emby-pv
     persistentVolumeClaim:
       claimName: emby-pvc
   - name: movies
     hostPath:
       path: /mnt/emby_unified/Movies
       type: Directory
   - name: tvshows
     hostPath:
       path: /mnt/emby_unified/TVShows
       type: Directory
```

### For Existing Deployments

1. Stop the affected containers
2. Recreate pods/Deployments with `hostPath` volumes pointing at `/mnt/emby_unified` instead of raw tier paths
3. Run manual library rescan in each app (Emby: Library → Update Library; Sonarr/Radarr: Library → Rescan)
4. Verify files are visible after rescan

### Guard Against Reboot Race Condition

Add an `initContainer` to ensure MergerFS/GeeseFS is mounted before app starts:

```yaml
initContainers:
  - name: wait-for-unified-mount
    image: busybox
    command: ["sh", "-c", "until mountpoint -q /mnt/emby_unified; do sleep 2; done"]
    volumeMounts:
      - name: emby-pv
        mountPath: /mnt/emby_unified
```

## Related

- `CONTEXT.md` — Glossary term `storage-app-integration`
- `ref/mergerFS/readme.md` — Original tiering architecture documentation
- `ref/mergerFS/cascade_tier.sh` — Nightly tier migration script
- `ref/mergerFS/setup_stack.md` — Stack configuration changes for Emby/Radarr/Sonarr