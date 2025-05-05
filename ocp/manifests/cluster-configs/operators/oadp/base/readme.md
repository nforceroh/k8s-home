```
cat <<EOF >/tmp/ocp
[default]
aws_access_key_id=ocp
aws_secret_access_key=ocp!123!ocp
EOF

```

oc create secret generic ocp-current-creds -n openshift-adp --from-file bsl=/tmp/ocp --dry-run -o yaml

oc create secret generic cloud-credentials --namespace openshift-adp --from-file cloud=s3credentials 

elero backup-location create ocp-current     --provider aws     --bucket ocp-current     --config profile=default,region=nf,insecureSkipTLSVerify=true,s3ForcePathStyle=true,s3Url=http://minio.ocp.nf.lab:10106     --prefix ocp   
  --credential cloud-credentials=cloud
velero backup-location create ocp-current \
    --provider aws \
    --bucket ocp-current \
    --config profile=default,region=nf,insecureSkipTLSVerify=true,s3ForcePathStyle=true,s3Url=http://minio.ocp.nf.lab:10106 \
    --prefix ocp \
    --credential ocp-current-creds=bsl

#https://docs.openshift.com/container-platform/4.10/backup_and_restore/application_backup_and_restore/installing/installing-oadp-aws.html

https://faun.pub/reconfiguring-your-kubernetes-backups-t aken-with-velero-to-a-new-location-67920ff16821
https://vmwire.com/2022/04/20/using-velero-with-restic-for-kubernetes-data-protection/
https://cloud.redhat.com/blog/how-to-backup-and-restore-stateful-applications-on-openshift-using-oadp-and-odf

velero client config set namespace=openshift-adp
velero schedule create iot-grafana --schedule="0 1 * * *" --ttl 168h0m0s  --selector app=grafana --include-namespaces iot --default-volumes-to-restic
velero schedule create iot-mosquitto --schedule="0 1 * * *" --ttl 168h0m0s  --selector app=mosquitto --include-namespaces iot --default-volumes-to-restic
velero schedule create mail-rainloop --schedule="0 2 * * *" --ttl 168h0m0s  --selector app=rainloop --include-namespaces mail --default-volumes-to-restic
velero schedule create mail-rspamd --schedule="0 2 * * *" --ttl 168h0m0s  --selector app=rspamd --include-namespaces mail --default-volumes-to-restic
velero schedule create mail-dovecot --schedule="0 10 * * *" --ttl 168h0m0s  --selector app=dovecot --include-namespaces mail --default-volumes-to-restic
velero schedule create minecraft-mc2 --schedule="0 3 * * *" --ttl 168h0m0s  --selector app=mc2 --include-namespaces minecraft --default-volumes-to-restic

oc -n torrent annotate deployment/deluge backup.velero.io/backup-volumes-excludes=data
oc -n torrent annotate deployment/emby backup.velero.io/backup-volumes-excludes=tvshows,movies
oc -n torrent annotate deployment/radarr backup.velero.io/backup-volumes-excludes=movies,downloads
oc -n torrent annotate deployment/sickchill backup.velero.io/backup-volumes-excludes=tvshows,downloads

oc -n torrent patch deployment/deluge -p '{"spec": {"template":{"metadata":{"annotations":{"backup.velero.io/backup-volumes-excludes":"data"}}}} }'
oc -n torrent patch deployment/emby -p '{"spec": {"template":{"metadata":{"annotations":{"backup.velero.io/backup-volumes-excludes":"tvshows,movies,new"}}}} }'
oc -n torrent patch deployment/radarr -p '{"spec": {"template":{"metadata":{"annotations":{"backup.velero.io/backup-volumes-excludes":"movies,downloads"}}}} }'
oc -n torrent patch deployment/sickchill -p '{"spec": {"template":{"metadata":{"annotations":{"backup.velero.io/backup-volumes-excludes":"tvshows,downloads"}}}} }'

# Daily Backup, 7 days retention policy
#velero schedule create duokey-bkup-daily-ret-7d --schedule="0 0 * * *" --ttl 168h0m0s --selector app=duokey

velero schedule create torrent-deluge --schedule="0 0 * * *" --ttl 168h0m0s  --selector app=deluge --include-namespaces torrent --default-volumes-to-restic
velero schedule create torrent-emby --schedule="0 0 * * *" --ttl 168h0m0s  --selector app=emby --include-namespaces torrent --default-volumes-to-restic
velero schedule create torrent-jackett --schedule="0 0 * * *" --ttl 168h0m0s  --selector app=jackett --include-namespaces torrent --default-volumes-to-restic
velero schedule create torrent-ombi --schedule="0 0 * * *" --ttl 168h0m0s  --selector app=ombi --include-namespaces torrent --default-volumes-to-restic
velero schedule create torrent-radarr --schedule="0 0 * * *" --ttl 168h0m0s  --selector app=radarr --include-namespaces torrent --default-volumes-to-restic
velero schedule create torrent-sickchill --schedule="0 0 * * *" --ttl 168h0m0s  --selector app=sickchill --include-namespaces torrent --default-volumes-to-restic



velero create backup databases-ns --include-namespaces databases --default-volumes-to-restic --ttl 168h0m0s
velero create backup iot-ns --include-namespaces iot --default-volumes-to-restic --ttl 168h0m0s
velero create backup mail-ns --include-namespaces mail --default-volumes-to-restic --ttl 168h0m0s
velero create backup minecraft-ns --include-namespaces minecraft --default-volumes-to-restic --ttl 168h0m0s
velero create backup tools-ns --include-namespaces tools --default-volumes-to-restic --ttl 168h0m0s
velero create backup torrent-ns --include-namespaces torrent --default-volumes-to-restic --ttl 3h0m0s

velero create backup registry-ns --include-namespaces openshift-image-registry --default-volumes-to-restic --ttl 168h0m0s

velero create restore --from-backup iot-ns
velero create restore --from-backup databases-ns
velero create restore --from-backup mail-ns
velero create restore --from-backup minecraft-ns
velero create restore --from-backup tools-ns
velero create restore --from-backup torrent-ns
velero create restore --from-backup registry-ns


# cron times are in UTC!!!!
```
velero schedule create databases-influxdb --schedule="30 2 * * *" --ttl 168h0m0s  --selector app=influxdb --include-namespaces databases --include-resources '*' --default-volumes-to-fs-backup
velero schedule create databases-redis --schedule="35 2 * * *" --ttl 168h0m0s  --selector app=redis --include-namespaces databases --include-resources '*'  --default-volumes-to-fs-backup
velero schedule create iot-grafana --schedule="45 2 * * *" --ttl 168h0m0s  --selector app=grafana --include-namespaces databases --include-resources '*'  --default-volumes-to-fs-backup
velero schedule create iot-nodered --schedule="45 2 * * *" --ttl 168h0m0s  --selector app=nodered --include-namespaces databases --include-resources '*'  --default-volumes-to-fs-backup
velero schedule create mail-rspamd --schedule="40 2 * * *" --ttl 168h0m0s  --selector app=rspamd --include-namespaces mail --include-resources '*'  --default-volumes-to-fs-backup
velero schedule create mail-dovecot --schedule="0 2 * * *" --ttl 168h0m0s  --selector app=dovecot --include-namespaces mail --include-resources '*'  --default-volumes-to-fs-backup
velero schedule create minecraft-mc1 --schedule="0 12 * * *" --ttl 168h0m0s  --selector app=mc1 --include-namespaces minecraft --include-resources '*'  --default-volumes-to-fs-backup
velero schedule create minecraft-mc2 --schedule="0 12 * * *" --ttl 168h0m0s  --selector app=mc2 --include-namespaces minecraft --include-resources '*'  --default-volumes-to-fs-backup
velero schedule create torrent-emby --schedule="0 3 * * *" --ttl 168h0m0s  --selector app=emby --include-namespaces torrent --include-resources '*'  --default-volumes-to-fs-backup
velero schedule create torrent-jellyseerr --schedule="15 3 * * *" --ttl 168h0m0s  --selector app=jellyseerr --include-namespaces torrent --include-resources '*'  --default-volumes-to-fs-backup
velero schedule create torrent-lidarr --schedule="15 3 * * *" --ttl 168h0m0s  --selector app=lidarr --include-namespaces torrent --include-resources '*'  --default-volumes-to-fs-backup
velero schedule create torrent-prowlarr --schedule="15 3 * * *" --ttl 168h0m0s  --selector app=prowlarr --include-namespaces torrent --include-resources '*'  --default-volumes-to-fs-backup
velero schedule create torrent-radarr --schedule="15 3 * * *" --ttl 168h0m0s  --selector app=radarr --include-namespaces torrent --include-resources '*'  --default-volumes-to-fs-backup
velero schedule create torrent-sonarr --schedule="15 3 * * *" --ttl 168h0m0s  --selector app=sonarr --include-namespaces torrent --include-resources '*'  --default-volumes-to-fs-backup
```

velero create backup mail-dovecot --selector app=dovecot --include-namespaces mail --default-volumes-to-fs-backup --ttl 3h0m0s
velero create backup databases-influxdb --selector app=influxdb --include-namespaces databases --default-volumes-to-fs-backup --ttl 3h0m0s

velero create backup iot-grafana --selector app=grafana --include-namespaces iot --default-volumes-to-fs-backup --ttl 3h0m0s
velero create backup minecraft-mc1 --selector app=mc1 --include-namespaces minecraft --default-volumes-to-fs-backup --ttl 24h0m0s
velero create backup minecraft-mc2 --selector app=mc2 --include-namespaces minecraft --default-volumes-to-fs-backup --ttl 24h0m0s



```
oc -n torrent patch deployment/emby -p '{"spec": {"template":{"metadata":{"annotations":{"backup.velero.io/backup-volumes-excludes":"tvshows,movies"}}}} }'
oc -n torrent patch deployment/lidarr -p '{"spec": {"template":{"metadata":{"annotations":{"backup.velero.io/backup-volumes-excludes":"music,torrent"}}}} }'
oc -n torrent patch deployment/radarr -p '{"spec": {"template":{"metadata":{"annotations":{"backup.velero.io/backup-volumes-excludes":"movies,torrent"}}}} }'
oc -n torrent patch deployment/sonarr -p '{"spec": {"template":{"metadata":{"annotations":{"backup.velero.io/backup-volumes-excludes":"tvshows,torrent"}}}} }'

velero create restore --from-backup iot-grafana2 --restore-volumes=true --include-resources pods,persistentvolumeclaims,persistentvolumes
velero create restore --from-backup iot-nodered --restore-volumes=true --include-resources pods,persistentvolumeclaims,persistentvolumes
velero create restore --from-backup minecraft-mc1 --restore-volumes=true --include-resources pods,persistentvolumeclaims,persistentvolumes
velero create restore --from-backup minecraft-mc2 --restore-volumes=true  --include-resources pods,persistentvolumeclaims,persistentvolumes
velero create restore --from-backup mail-dovecot --restore-volumes=true
velero create restore --from-backup databases-influxdb --restore-volumes=true --include-resources pods,persistentvolumeclaims,persistentvolumes,configmaps,secrets

```

```
# create backups from schedules
for s in `velero get schedule|grep -v NAME|awk '{print $1}'`; do velero create backup --from-schedule $s;done

# delete backups
for s in `velero get backup|grep -v NAME|awk '{print $1}'`; do velero delete backup $s --confirm;done
```
velero restore create emby \
  --from-backup torrent-emby-20230802175158 \
  --namespace-mappings torrent:temp

oc apply -f -<<EOF
apiVersion: v1
kind: ConfigMap
metadata:
  # any name can be used; Velero uses the labels (below)
  # to identify it rather than the name
  name: change-storage-class-config
  # must be in the velero namespace
  namespace: velero
  # the below labels should be used verbatim in your
  # ConfigMap.
  labels:
    # this value-less label identifies the ConfigMap as
    # config for a plugin (i.e. the built-in restore item action plugin)
    velero.io/plugin-config: ""
    # this label identifies the name and kind of plugin
    # that this ConfigMap is for.
    velero.io/change-storage-class: RestoreItemAction
data:
  # add 1+ key-value pairs here, where the key is the old
  # storage class name and the value is the new storage
  # class name.
  <old-storage-class>: <new-storage-class>
EOF