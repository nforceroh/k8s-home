# Get velero cli
```
VERSION=v1.15.2
mkdir -p ~/.local/bin
wget -c https://github.com/vmware-tanzu/velero/releases/download/${VERSION}/velero-${VERSION}-linux-amd64.tar.gz
tar xvfz velero-${VERSION}-linux-amd64.tar.gz
sudo install -o root -g root -m 755 velero-${VERSION}-linux-amd64/velero /usr/local/bin
mv velero*/velero ~/.local/bin
rm -rf velero-*
chmod +x ~/.local/bin/velero
```

```
kubectl patch deployment velero -n velero --patch \
'{"spec":{"template":{"spec":{"containers":[{"name": "velero", "resources": {"requests": {"cpu": "2"}}}]}}}}'
kubectl patch daemonset node-agent -n velero --patch \
'{"spec":{"template":{"spec":{"containers":[{"name": "node-agent", "resources": {"requests": {"cpu": "2"}}}]}}}}'


kubectl patch deployment velero -n velero --patch \
'{"spec":{"template":{"spec":{"containers":[{"name": "velero", "resources": {"limits":{"cpu": "2", "memory": "4Gi"}, "requests": {"cpu": "1", "memory": "128Mi"}}}]}}}}'

kubectl patch daemonset node-agent -n velero --patch \
'{"spec":{"template":{"spec":{"containers":[{"name": "node-agent", "resources": {"limits":{"cpu": "2", "memory": "4Gi"}, "requests": {"cpu": "1", "memory": "512Mi"}}}]}}}}'
```

#https://docs.openshift.com/container-platform/4.10/backup_and_restore/application_backup_and_restore/installing/installing-oadp-aws.html

https://faun.pub/reconfiguring-your-kubernetes-backups-t aken-with-velero-to-a-new-location-67920ff16821
https://vmwire.com/2022/04/20/using-velero-with-restic-for-kubernetes-data-protection/
https://cloud.redhat.com/blog/how-to-backup-and-restore-stateful-applications-on-openshift-using-oadp-and-odf


oc -n torrent annotate deployment/deluge backup.velero.io/backup-volumes-excludes=data
oc -n torrent annotate deployment/emby backup.velero.io/backup-volumes-excludes=tvshows,movies
oc -n torrent annotate deployment/radarr backup.velero.io/backup-volumes-excludes=movies,downloads
oc -n torrent annotate deployment/sickchill backup.velero.io/backup-volumes-excludes=tvshows,downloads

oc -n torrent patch deployment/deluge -p '{"spec": {"template":{"metadata":{"annotations":{"backup.velero.io/backup-volumes-excludes":"data"}}}} }'
oc -n torrent patch deployment/emby -p '{"spec": {"template":{"metadata":{"annotations":{"backup.velero.io/backup-volumes-excludes":"tvshows,movies,new"}}}} }'
oc -n torrent patch deployment/radarr -p '{"spec": {"template":{"metadata":{"annotations":{"backup.velero.io/backup-volumes-excludes":"movies,downloads"}}}} }'
oc -n torrent patch deployment/sickchill -p '{"spec": {"template":{"metadata":{"annotations":{"backup.velero.io/backup-volumes-excludes":"tvshows,downloads"}}}} }'

# cron times are in UTC!!!! so add 4hr to current time
```
velero schedule create databases-influxdb --schedule="30 4 * * *" --ttl 168h0m0s  --selector app=influxdb --include-namespaces databases --include-resources '*' --default-volumes-to-fs-backup
velero schedule create databases-redis --schedule="35 4 * * *" --ttl 168h0m0s  --selector app=redis --include-namespaces databases --include-resources '*'  --default-volumes-to-fs-backup
velero schedule create databases-mariadb --schedule="40 4 * * *" --ttl 168h0m0s  --selector app=mariadb --include-namespaces databases --include-resources '*'  --default-volumes-to-fs-backup
velero schedule create harbor-harbor --schedule="45 4 * * *" --ttl 168h0m0s  --selector app=harbor --include-namespaces harbor --include-resources '*'  --default-volumes-to-fs-backup
velero schedule create iot-grafana --schedule="0 5 * * *" --ttl 168h0m0s  --selector app=grafana --include-namespaces databases --include-resources '*'  --default-volumes-to-fs-backup
velero schedule create iot-nodered --schedule="0 5 * * *" --ttl 168h0m0s  --selector app=nodered --include-namespaces databases --include-resources '*'  --default-volumes-to-fs-backup
velero schedule create mail-rspamd --schedule="10 4 * * *" --ttl 168h0m0s  --selector app=rspamd --include-namespaces mail --include-resources '*'  --default-volumes-to-fs-backup
velero schedule create mail-dovecot --schedule="15 4 * * *" --ttl 168h0m0s  --selector app=dovecot --include-namespaces mail --include-resources '*'  --default-volumes-to-fs-backup
#velero schedule create minecraft-mc1 --schedule="0 12 * * *" --ttl 168h0m0s  --selector app=mc1 --include-namespaces minecraft --include-resources '*'  --default-volumes-to-fs-backup
#velero schedule create minecraft-mc2 --schedule="0 12 * * *" --ttl 168h0m0s  --selector app=mc2 --include-namespaces minecraft --include-resources '*'  --default-volumes-to-fs-backup
velero schedule create torrent-emby --schedule="0 5 * * *" --ttl 168h0m0s  --selector app=emby --include-namespaces torrent --include-resources '*'  --default-volumes-to-fs-backup
velero schedule create torrent-jellyseerr --schedule="15 7 * * *" --ttl 168h0m0s  --selector app=jellyseerr --include-namespaces torrent --include-resources '*'  --default-volumes-to-fs-backup
velero schedule create torrent-lidarr --schedule="20 7 * * *" --ttl 168h0m0s  --selector app=lidarr --include-namespaces torrent --include-resources '*'  --default-volumes-to-fs-backup
velero schedule create torrent-prowlarr --schedule="25 7 * * *" --ttl 168h0m0s  --selector app=prowlarr --include-namespaces torrent --include-resources '*'  --default-volumes-to-fs-backup
velero schedule create torrent-radarr --schedule="30 7 * * *" --ttl 168h0m0s  --selector app=radarr --include-namespaces torrent --include-resources '*'  --default-volumes-to-fs-backup
velero schedule create torrent-sonarr --schedule="35 7 * * *" --ttl 168h0m0s  --selector app=sonarr --include-namespaces torrent --include-resources '*'  --default-volumes-to-fs-backup
velero schedule create smallstep-step-ca --schedule="40 7 * * *" --ttl 168h0m0s  --selector app=step-ca --include-namespaces smallstep --include-resources '*'  --default-volumes-to-fs-backup
velero schedule create tools-kms --schedule="40 7 * * *" --ttl 168h0m0s  --selector app=kms --include-namespaces tools --include-resources '*'  --default-volumes-to-fs-backup
velero schedule create ai-open-webui --schedule="40 7 * * *" --ttl 168h0m0s  --selector app=sopen-webui --include-namespaces ai --include-resources '*'  --default-volumes-to-fs-backup
```

# cron times are in UTC!!!! so add 4hr to current time Weekly backup to idrive 9 days ttl
```
velero schedule create idrive-databases-influxdb --schedule="0 7 * * 1" --ttl 216h0m0s  --selector app=influxdb --include-namespaces databases --include-resources '*'
velero schedule create idrive-databases-redis --schedule="15 7 * * 1" --ttl 216h0m0s  --selector app=redis --include-namespaces databases --include-resources '*'
velero schedule create idrive-databases-mariadb --schedule="30 7 * * 1" --ttl 216h0m0s  --selector app=mariadb --include-namespaces databases --include-resources '*'
velero schedule create idrive-harbor-harbor --schedule="45 7 * * 1" --ttl 216h0m0s  --selector app=harbor --include-namespaces harbor --include-resources '*'
velero schedule create idrive-iot-grafana --schedule="0 8 * * 1" --ttl 216h0m0s  --selector app=grafana --include-namespaces databases --include-resources '*'
velero schedule create idrive-iot-nodered --schedule="15 8 * * 1" --ttl 216h0m0s  --selector app=nodered --include-namespaces databases --include-resources '*'
velero schedule create idrive-mail-rspamd --schedule="30 8 * * 1" --ttl 216h0m0s  --selector app=rspamd --include-namespaces mail --include-resources '*'
velero schedule create idrive-mail-dovecot --schedule="45 8 * * 1" --ttl 216h0m0s  --selector app=dovecot --include-namespaces mail --include-resources '*'
#velero schedule create idrive-minecraft-mc1 --schedule="0 12 * * 1" --ttl 216h0m0s  --selector app=mc1 --include-namespaces minecraft --include-resources '*'
#velero schedule create idrive-minecraft-mc2 --schedule="0 12 * * 1" --ttl 216h0m0s  --selector app=mc2 --include-namespaces minecraft --include-resources '*'
velero schedule create idrive-torrent-emby --schedule="0 9 * * 1" --ttl 216h0m0s  --selector app=emby --include-namespaces torrent --include-resources '*'
velero schedule create idrive-torrent-jellyseerr --schedule="10 9 * * 1" --ttl 216h0m0s  --selector app=jellyseerr --include-namespaces torrent --include-resources '*'
velero schedule create idrive-torrent-lidarr --schedule="20 9 * * 1" --ttl 216h0m0s  --selector app=lidarr --include-namespaces torrent --include-resources '*'
velero schedule create idrive-torrent-prowlarr --schedule="25 9 * * 1" --ttl 216h0m0s  --selector app=prowlarr --include-namespaces torrent --include-resources '*'
velero schedule create idrive-torrent-radarr --schedule="30 9 * * 1" --ttl 216h0m0s  --selector app=radarr --include-namespaces torrent --include-resources '*'
velero schedule create idrive-torrent-sonarr --schedule="35 9 * * 1" --ttl 216h0m0s  --selector app=sonarr --include-namespaces torrent --include-resources '*'
velero schedule create idrive-smallstep-step-ca --schedule="40 9 * * 1" --ttl 216h0m0s  --selector app=step-ca --include-namespaces smallstep --include-resources '*'
velero schedule create idrive-tools-kms --schedule="45 9 * * 1" --ttl 216h0m0s  --selector app=kms --include-namespaces tools --include-resources '*'
velero schedule create idrive-ai-open-webui3 --schedule="27 9 * * *" --ttl 216h0m0s  --selector app.kubernetes.io/instance=open-webui --include-namespaces ai --include-resources '*'
velero schedule create cf-ai-open-webui --schedule="27 9 * * *" --ttl 216h0m0s  --selector app.kubernetes.io/instance=open-webui --include-namespaces ai --include-resources '*' --storage-location cloudfront
```

```
velero create backup idrive-databases-influxdb --ttl 216h0m0s  --selector app=influxdb --include-namespaces databases --include-resources '*' --default-volumes-to-fs-backup --storage-location idrive
velero create backup idrive-databases-redis --ttl 216h0m0s  --selector app=redis --include-namespaces databases --include-resources '*'  --default-volumes-to-fs-backup --storage-location idrive
velero create backup idrive-databases-mariadb --ttl 216h0m0s  --selector app=mariadb --include-namespaces databases --include-resources '*'  --default-volumes-to-fs-backup --storage-location idrive
#velero create backup idrive-harbor-harbor --ttl 216h0m0s  --selector app=harbor --include-namespaces harbor --include-resources '*'  --default-volumes-to-fs-backup --storage-location idrive
velero create backup idrive-iot-grafana --ttl 216h0m0s  --selector app=grafana --include-namespaces databases --include-resources '*'  --default-volumes-to-fs-backup --storage-location idrive
velero create backup idrive-iot-nodered --ttl 216h0m0s  --selector app=nodered --include-namespaces databases --include-resources '*'  --default-volumes-to-fs-backup --storage-location idrive
velero create backup idrive-mail-rspamd --ttl 216h0m0s  --selector app=rspamd --include-namespaces mail --include-resources '*'  --default-volumes-to-fs-backup --storage-location idrive
velero create backup idrive-mail-dovecot --ttl 216h0m0s  --selector app=dovecot --include-namespaces mail --include-resources '*'  --default-volumes-to-fs-backup --storage-location idrive
#velero create backup idrive-minecraft-mc1 --ttl 216h0m0s  --selector app=mc1 --include-namespaces minecraft --include-resources '*'  --default-volumes-to-fs-backup --storage-location idrive
#velero create backup idrive-minecraft-mc2 ---ttl 216h0m0s  --selector app=mc2 --include-namespaces minecraft --include-resources '*'  --default-volumes-to-fs-backup --storage-location idrive
velero create backup idrive-torrent-emby --ttl 216h0m0s  --selector app=emby --include-namespaces torrent --include-resources '*'  --default-volumes-to-fs-backup --storage-location idrive
velero create backup idrive-torrent-jellyseerr --ttl 216h0m0s  --selector app=jellyseerr --include-namespaces torrent --include-resources '*'  --default-volumes-to-fs-backup --storage-location idrive
velero create backup idrive-torrent-lidarr --ttl 216h0m0s  --selector app=lidarr --include-namespaces torrent --include-resources '*'  --default-volumes-to-fs-backup --storage-location idrive
velero create backup idrive-torrent-prowlarr --ttl 216h0m0s  --selector app=prowlarr --include-namespaces torrent --include-resources '*'  --default-volumes-to-fs-backup --storage-location idrive
velero create backup idrive-torrent-radarr --ttl 216h0m0s  --selector app=radarr --include-namespaces torrent --include-resources '*'  --default-volumes-to-fs-backup --storage-location idrive
velero create backup idrive-torrent-sonarr --ttl 216h0m0s  --selector app=sonarr --include-namespaces torrent --include-resources '*'  --default-volumes-to-fs-backup --storage-location idrive
velero create backup idrive-smallstep-step-ca --ttl 216h0m0s  --selector app=step-ca --include-namespaces smallstep --include-resources '*'  --default-volumes-to-fs-backup --storage-location idrive
velero create backup idrive-tools-kms --ttl 216h0m0s  --selector app=kms --include-namespaces tools --include-resources '*'  --default-volumes-to-fs-backup --storage-location idrive
velero create backup cf-ai-open-webui --ttl 216h0m0s  --selector app=open-webui --include-namespaces ai --include-resources '*'  --default-volumes-to-fs-backup --storage-location cloudfront
velero create backup cf-mail-dovecot --ttl 216h0m0s  --selector app=dovecot --include-namespaces mail --include-resources '*'  --default-volumes-to-fs-backup --storage-location cloudflared


```
kubectl -n torrent patch deployment/emby -p '{"spec": {"template":{"metadata":{"annotations":{"backup.velero.io/backup-volumes-excludes":"tvshows,movies"}}}} }'
kubectl -n torrent patch deployment/lidarr -p '{"spec": {"template":{"metadata":{"annotations":{"backup.velero.io/backup-volumes-excludes":"music,torrent"}}}} }'
kubectl -n torrent patch deployment/radarr -p '{"spec": {"template":{"metadata":{"annotations":{"backup.velero.io/backup-volumes-excludes":"movies,torrent"}}}} }'
kubectl -n torrent patch deployment/sonarr -p '{"spec": {"template":{"metadata":{"annotations":{"backup.velero.io/backup-volumes-excludes":"tvshows,torrent"}}}} }'
kubectl -n torrent patch deployment/deluge -p '{"spec": {"template":{"metadata":{"annotations":{"backup.velero.io/backup-volumes-excludes":"torrent"}}}} }'

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
for s in `velero get backup|grep Failed|grep -v NAME|awk '{print $1}'`; do velero delete backup $s --confirm;done
```
velero restore create emby \
  --from-backup torrent-emby-20230802175158 \
  --namespace-mappings torrent:temp

kubectl apply -f -<<EOF
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
  truenas-iscsi: openebs-zfspv-lz4
EOF

# PVC only restore

SELECTOR="harbor"
velero create backup mig-${SELECTOR}   --selector app=${SELECTOR} --include-namespaces harbor --include-resources '*'  --default-volumes-to-fs-backup 
watch velero backup describe mig-${SELECTOR} --details

#kubectl patch pv <your-pv-name> -p "{\"spec\":{\"persistentVolumeReclaimPolicy\":\"Retain\"}}"
velero restore create --from-backup mig-${SELECTOR} --restore-volumes=true

for SELECTOR in emby bazarr deluge jellyseerr lidarr prowlarr radarr sonarr; do
  velero create backup mig-${SELECTOR}  --selector app=${SELECTOR} --include-namespaces torrent --include-resources '*'  --default-volumes-to-fs-backup
done


for SELECTOR in jellyseerr; do
  velero restore create --from-backup mig-${SELECTOR} --restore-volumes=true
  sleep 10
done

# Using ns for cross cluster, need to disable snapshots
```
NS="torrent"
velero create backup mig-ns-${NS}-new  --include-namespaces ${NS} --include-resources '*'  --default-volumes-to-fs-backup --snapshot-volumes=false --storage-location idrive
watch velero backup describe mig-ns-${NS}-new --details

NS="iot"
velero restore create --from-backup nas02-mig-ns-${NS} --restore-volumes=true

```
for ns in mail databases iot; do
 velero create backup nas02-mig-ns-${ns}  --include-namespaces ${ns} --include-resources '*'  --default-volumes-to-fs-backup --snapshot-volumes=false --storage-location idrive
done
