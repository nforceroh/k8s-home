# Stack Configuration Changes for Tiered Storage

This document covers the changes needed in **Emby**, **Radarr**, and **Sonarr** so they work correctly with the 3-tier cascading storage architecture (see `README.md`). It assumes the MergerFS unified pool is mounted at `/mnt/emby_unified` per Section 3 of the README.

## The core problem

`cascade_tier.sh` physically relocates files between `/mnt/hdd01/emby` (HOT), `/mnt/nfs_emby` (WARM), and `/mnt/r2_emby` (COLD) as they age. **Any application whose volume points directly at one of those raw tier paths will lose visibility of a file the moment it migrates to a different tier.**

The fix is the same for every app in this stack: **point library/media volumes at the unified MergerFS mount (`/mnt/emby_unified`), never at a raw tier path.** MergerFS transparently resolves a file to whichever tier it currently lives on, so the app never notices a migration happened.

Changing a pod's `hostPath.path` (the node-side source) does **not** require changing the container's `mountPath` or any path an app has stored internally (library root folders, tracked file paths, etc.) — those stay identical from the container's point of view. Only the node-side source changes.

---

## Emby

**Problem:** the current deployment mounts `movies` and `tvshows` directly from `/mnt/hdd01/emby/Movies` and `/mnt/hdd01/emby/TVShows` — the raw HOT tier — bypassing the unified pool entirely. Once a file ages into WARM or COLD, it silently disappears from Emby's library view (the file still exists on disk, just not at the path the container is mounting).

**Fix:** point both volumes at the unified mount instead:

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

**Also worth resolving:** if `emby-pv`/`emby-pvc` already resolves to `/mnt/emby_unified` (per the `emby-storage.yaml` PV/PVC in the README's Kubernetes Integration section), the separate `movies`/`tvshows` hostPath volumes are likely redundant with it. Consider consolidating to a single PVC mounted once, with `movies`/`tvshows` as `subPath: Movies` / `subPath: TVShows` mounts of that same volume, rather than three independent volume definitions pointing at overlapping trees.

**Mount-ordering risk:** a `hostPath` volume is a snapshot bind-mount taken when the pod starts — Kubernetes does not wait for MergerFS to actually be mounted on top of `/mnt/emby_unified` first. If the pod starts before the fstab-driven mounts finish coming up (e.g. right after a reboot, or while GeeseFS is still retrying past a transient Cloudflare 522), Emby could bind-mount an empty directory and never see it populate afterward. Guard against this with an `initContainer`:

```yaml
      initContainers:
        - name: wait-for-unified-mount
          image: busybox
          command: ["sh", "-c", "until mountpoint -q /mnt/emby_unified; do sleep 2; done"]
          volumeMounts:
            - name: emby-pv
              mountPath: /mnt/emby_unified
```

---

## Radarr & Sonarr

Radarr and Sonarr have an extra wrinkle beyond Emby: they don't just *read* the library, they **track exact file paths in their database**, actively manage files (rename, move, delete, quality upgrades), and run health checks that flag a tracked file as **missing** if it's not found at the expected path — which can trigger an unwanted re-download.

### 1. Root folder (library) path — same fix as Emby

The **root folder** configured in each app's Settings → Media Management (e.g. `/movies`, `/tv` inside the container) must map to the unified mount, not a raw tier:

```yaml
        - name: movies
          hostPath:
            path: /mnt/emby_unified/Movies
            type: Directory
        - name: tvshows
          hostPath:
            path: /mnt/emby_unified/TVShows
            type: Directory
```

As long as the container's `mountPath` (e.g. `/movies`) doesn't change, Radarr/Sonarr's internally tracked paths don't need any remapping — only the node-side `hostPath.path` changes. Once fixed, files that get migrated by `cascade_tier.sh` continue to resolve correctly and Radarr/Sonarr won't flag them as missing.

**If you've already been running with root folders pointed at the raw HOT path:** run a manual library rescan (Radarr/Sonarr → Library → *Update Library* / *Rescan*) after applying the fix, so each app re-verifies file health against the now-correct unified path.

### 2. Downloads folder — keep this separate, and ideally on HOT

Radarr/Sonarr's **download client category / completed-downloads folder** (where your download client drops finished files before Radarr/Sonarr imports them into the library) should **not** be inside the tiering pool at all — it's a staging area, not library storage. Point it at a dedicated path on the HOT tier's local filesystem, e.g.:

```yaml
        - name: downloads
          hostPath:
            path: /mnt/hdd01/emby/downloads
            type: Directory
```

This is standard Radarr/Sonarr best practice independent of this tiering setup, but it matters more here for two reasons:

- **Import speed.** Freshly downloaded files are large and need to land somewhere fast; writing straight to NFS or (worst case) R2 during import would be slow and, for R2, adds egress/API costs for something about to be moved again almost immediately.
- **Hardlink behavior.** If "Use Hardlinks instead of Copy" is enabled (recommended, avoids doubling disk I/O on import), hardlinks only work **within the same filesystem**. The downloads folder and the destination the file lands on need to be the same underlying filesystem for a hardlink to succeed.

### 3. The hardlink / MergerFS create-policy interaction (read this if using hardlinks)

This is the one genuinely tricky part. MergerFS's `category.create=epmfs` policy (used for the unified pool per the README) creates new files on whichever *existing* branch (HOT/WARM/COLD) has the most free space among branches that already contain the parent folder. Since `Movies`/`TVShows` folders typically exist on all three branches once any migration has happened, a **newly imported file is not guaranteed to land on HOT** — it could land on WARM or even COLD if those happen to have more free space at that moment.

Consequences:

- If the new import lands on a different filesystem than your downloads folder, the hardlink will silently fail and Radarr/Sonarr will fall back to a copy. This is not a correctness problem — the file still ends up in the right place — but it does mean extra local I/O and a moment of doubled disk usage instead of an instant hardlink.
- It's not harmful for cascade tiering logic either: `cascade_tier.sh` only moves files based on file age (`mtime`), so a freshly imported file — regardless of which physical branch it initially lands on — won't be swept into a lower tier until it actually ages past your configured `--hot-days`/`--warm-days` thresholds.

If you want new imports to reliably land on HOT (for guaranteed hardlink success and consistent fast access to recently-added media), the cleanest option is to **bypass the unified mount for imports** the same way we already separate the downloads folder: point Radarr/Sonarr's root folder itself at a HOT-tier path for the *purpose of new imports*, and rely on Emby (and Radarr/Sonarr's own read access) going through the unified mount for everything else. In practice this usually isn't worth the added complexity — accepting the occasional copy-fallback is simpler and the performance difference is a one-time import cost, not an ongoing one.

### 4. Mount-ordering — same initContainer pattern as Emby, needed on both

Both pods now mount a volume backed by `/mnt/emby_unified` (`tvshows` for Sonarr, `movies` for Radarr), so they're subject to the exact same mount-ordering race as Emby: if the pod starts before MergerFS finishes mounting on top of that path, the volume bind-mounts an empty directory and never sees it populate afterward. The `torrent` volume does **not** need this guard — it's a plain local path (`/mnt/hdd01/torrent`), not dependent on the fstab-driven tier mounts coming up in a particular order.

**Sonarr — full manifest with the fix applied:**

```yaml
      initContainers:
        - name: wait-for-unified-mount
          image: busybox
          command: ["sh", "-c", "until mountpoint -q /mnt/emby_unified; do sleep 2; done"]
          volumeMounts:
            - name: tvshows
              mountPath: /mnt/emby_unified
      volumes:
        - name: sonarr-pv
          persistentVolumeClaim:
            claimName: sonarr-pvc
        - name: tvshows
          hostPath:
            path: /mnt/emby_unified/TVShows
            type: Directory
        - name: torrent
          hostPath:
            path: /mnt/hdd01/torrent
            type: Directory
```

**Radarr — full manifest with the fix applied:**

```yaml
      initContainers:
        - name: wait-for-unified-mount
          image: busybox
          command: ["sh", "-c", "until mountpoint -q /mnt/emby_unified; do sleep 2; done"]
          volumeMounts:
            - name: movies
              mountPath: /mnt/emby_unified
      volumes:
        - name: radarr-pv
          persistentVolumeClaim:
            claimName: radarr-pvc
        - name: movies
          hostPath:
            path: /mnt/emby_unified/Movies
            type: Directory
        - name: torrent
          hostPath:
            path: /mnt/hdd01/torrent
            type: Directory
```

Only the `tvshows`/`movies` `hostPath.path` changed from the original `/mnt/hdd01/emby/...` — `torrent` is untouched, since it was already correctly separated from the tiering pool.

**Note on `/mnt/hdd01/torrent`:** if this lives on the same ZFS dataset/pool as `/mnt/hdd01/emby` (the HOT tier), hardlinks will succeed whenever a new import happens to land on the HOT branch of the MergerFS pool — which is the common case, since a freshly downloaded file is brand new. If a new import instead lands on WARM or COLD under `epmfs`'s free-space policy, the hardlink falls back to a copy per the explanation in Section 3 above — not broken, just slightly slower.

---

## Verification checklist

After applying these changes to all three apps:

1. **Confirm health checks are clean.** In Radarr/Sonarr, check Settings → General → *no* "root folder missing" or unresolved health warnings.
2. **Simulate a migration and confirm visibility survives it.** Using the test procedure from the README's testing section (backdated test files + `cascade_tier.sh --path _tiertest`), verify:
   - Emby still shows the test media after it's migrated to WARM/COLD.
   - Radarr/Sonarr still report the corresponding tracked file as present (not missing) after migration — check the movie/episode's file details page.
3. **Confirm a real import still works end-to-end.** Let a real download complete and import; verify it appears in Emby immediately at `/mnt/emby_unified/...` without needing a manual library rescan.
4. **Reboot test.** Reboot the node and confirm all three pods come up healthy without needing manual intervention — this exercises the `initContainer` mount-wait logic against real boot-time mount ordering.x