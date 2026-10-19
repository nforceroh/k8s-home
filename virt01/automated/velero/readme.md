# Velero Backup Schedules

All backup schedules are now managed declaratively via **Argo CD** using the Velero installer. Schedules are defined as Kubernetes `Schedule` resources in `virt01/automated/velero/templates/` and synced to the cluster automatically.

## Schedule File Format

Files follow the naming convention: `$namespace-$app-schedule.yaml`

Each file contains two `Schedule` resources:
- **Daily local** - 7-day retention (168h), runs daily at staggered times
- **Weekly offsite** - 30-day retention (720h), runs weekly (Wednesday) with `snapshotMoveData: true` for offsite copy

## Current Schedules (23 apps, 46 schedules)

| Namespace | App | Daily (Local) | Weekly (Offsite) |
|-----------|-----|---------------|------------------|
| camera | frigate-config | 06:35 UTC | Wed 04:35 UTC |
| camera | scrypted | 06:40 UTC | Wed 06:40 UTC |
| databases | influxdb | 01:00 UTC | Wed 01:00 UTC |
| databases | postgresql | 01:20 UTC | Wed 01:20 UTC |
| databases | redis | 06:00 UTC | Wed 06:00 UTC |
| iot | mosquitto | 02:10 UTC | Wed 02:10 UTC |
| iot | nodered | 02:20 UTC | Wed 02:20 UTC |
| mail | dovecot | 03:00 UTC | Wed 03:00 UTC |
| mail | postfix | 03:15 UTC | Wed 03:15 UTC |
| mail | rspamd | 03:30 UTC | Wed 03:30 UTC |
| mail | snappymail | 03:40 UTC | Wed 03:40 UTC |
| media | aurral | 06:35 UTC | Wed 06:35 UTC |
| media | bazarr | 06:00 UTC | Wed 06:00 UTC |
| media | emby | 06:15 UTC | Wed 06:15 UTC |
| media | lidarr | 06:35 UTC | Wed 06:35 UTC |
| media | radarr | 06:50 UTC | Wed 06:50 UTC |
| media | sonarr | 07:00 UTC | Wed 07:00 UTC |
| smallstep | smallstep | 05:00 UTC | Wed 05:00 UTC |
| tools | kms | 05:00 UTC | Wed 05:00 UTC |
| tools | lubelog | 05:10 UTC | Wed 05:10 UTC |
| torrent | deluge | 06:10 UTC | Wed 06:10 UTC |
| torrent | prowlarr | 06:40 UTC | Wed 06:40 UTC |
| torrent | seerr | 06:30 UTC | Wed 04:30 UTC |

## Managing Schedules

### View all schedules
```bash
velero schedule get
```

### View schedule details
```bash
velero schedule get <schedule-name> -o yaml
```

### Trigger manual backup from schedule
```bash
velero backup create --from-schedule <schedule-name>
```

### Pause/Resume a schedule
```bash
velero schedule pause <schedule-name>
velero schedule resume <schedule-name>
```

### Delete a schedule (removes from cluster, repo is source of truth)
```bash
velero schedule delete <schedule-name>
# Then remove the file from virt01/automated/velero/templates/
```

## Adding a New Schedule

1. Create a new file in `virt01/automated/velero/templates/` named `$namespace-$app-schedule.yaml`
2. Use the template below, adjusting namespace, app label, and cron times
3. Commit and push - Argo CD will sync it

### Template
```yaml
apiVersion: velero.io/v1
kind: Schedule
metadata:
  name: $namespace-$app-daily-local
  namespace: velero
spec:
  schedule: CRON_TZ=America/New_York <MIN> <HOUR> * * *
  skipImmediately: false
  template:
    includedNamespaces:
      - $namespace
    includedResources:
      - '*'
    labelSelector:
      matchLabels:
        app.kubernetes.io/instance: $app
    ttl: 168h0m0s
    snapshotVolumes: true
    snapshotMoveData: false
---
apiVersion: velero.io/v1
kind: Schedule
metadata:
  name: $namespace-$app-weekly-offsite-cfr2
  namespace: velero
spec:
  schedule: CRON_TZ=America/New_York <MIN> <HOUR> * * 3
  skipImmediately: false
  template:
    includedNamespaces:
      - $namespace
    includedResources:
      - '*'
    labelSelector:
      matchLabels:
        app.kubernetes.io/instance: $app
    ttl: 720h0m0s
    snapshotVolumes: true
    snapshotMoveData: true
```

## Volume Exclusions

Add `backup.velero.io/backup-volumes-excludes` annotation to deployments to exclude large media directories:

```bash
# Example: exclude media directories from torrent apps
kubectl -n torrent patch deployment/deluge -p '{"spec":{"template":{"metadata":{"annotations":{"backup.velero.io/backup-volumes-excludes":"data"}}}}}'
kubectl -n media patch deployment/emby -p '{"spec":{"template":{"metadata":{"annotations{"backup.velero.io/backup-volumes-excludes":"tvshows,movies"}}}} }'
kubectl -n media patch deployment/radarr -p '{"spec":{"template":{"metadata":{"annotations{"backup.velero.io/backup-volumes-excludes":"movies,downloads"}}}} }'
```

## Restore Examples

```bash
# Restore from latest backup of a schedule
velero restore create --from-schedule media-sonarr-daily-local --restore-volumes=true

# Restore specific backup
velero restore create --from-backup media-sonarr-daily-local-20261019110000 --restore-volumes=true

# Cross-namespace restore
velero restore create --from-backup torrent-deluge-daily-local-20261019110000 --namespace-mappings torrent:temp --restore-volumes=true
```

## Storage Locations

- **local** (default) - Local MinIO/NFS, daily backups
- **cfr2** (offsite) - Cloudflare R2, weekly backups with `snapshotMoveData: true`

## References

- [Velero Schedule Documentation](https://velero.io/docs/v1.15/schedule-backup/)
- [Argo CD ApplicationSet for Velero](../appsConfigurator/templates/appsConfigurator-operators.yaml)
