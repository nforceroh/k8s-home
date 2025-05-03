#!/bin/bash

# namespace:app:cron:selector
schedules=(
  "ai:open-webui:CRON_TZ=America/New_York 0 4 * * *:app.kubernetes.io/instance"
  "common:smallstep:CRON_TZ=America/New_York 0 5 * * *:app.kubernetes.io/instance"
  "databases:influxdb:CRON_TZ=America/New_York 0 1 * * *:app"
  "databases:mariadb:CRON_TZ=America/New_York 10 1 * * *:app"
  "databases:postgresql:CRON_TZ=America/New_York 20 1 * * *:app"
  "databases:redis:CRON_TZ=America/New_York 0 6 * * *:app.kubernetes.io/instance"
  "iot:grafana:CRON_TZ=America/New_York 0 2 * * *:app"
  "iot:mosquitto:CRON_TZ=America/New_York 10 2 * * *:app"
  "iot:nodered:CRON_TZ=America/New_York 20 2 * * *:app"
  "mail:dovecot:CRON_TZ=America/New_York 0 3 * * *:app"
  "mail:postfix:CRON_TZ=America/New_York 15 3 * * *:app"
  "mail:rspamd:CRON_TZ=America/New_York 30 3 * * *:app"
  "mail:snappymail:CRON_TZ=America/New_York 40 3 * * *:app"
  "minecraft:mc2-minecraft:CRON_TZ=America/New_York 0 4 * * *:app.kubernetes.io/instance"
  "minecraft:seasons-minecraft:CRON_TZ=America/New_York 10 4 * * *:app.kubernetes.io/instance"
  "tools:kms:CRON_TZ=America/New_York 0 5 * * *:app"
  "tools:lubelog:CRON_TZ=America/New_York 10 5 * * *:app"
  "torrent:bazarr:CRON_TZ=America/New_York 0 6 * * *:app"
  "torrent:calibre:CRON_TZ=America/New_York 5 6 * * *:app"
  "torrent:deluge:CRON_TZ=America/New_York 10 6 * * *:app"
  "torrent:emby:CRON_TZ=America/New_York 15 6 * * *:app"
  "torrent:jellyseerr:CRON_TZ=America/New_York 30 6 * * *:app"
  "torrent:lidarr:CRON_TZ=America/New_York 35 6 * * *:app"
  "torrent:prowlarr:CRON_TZ=America/New_York 40 6 * * *:app"
  "torrent:radarr:CRON_TZ=America/New_York 50 6 * * *:app"
  "torrent:readarr:CRON_TZ=America/New_York 55 6 * * *:app"
  "torrent:sonarr:CRON_TZ=America/New_York 0 7 * * *:app"
)

for schedule in "${schedules[@]}"; do
  IFS=':' read -r namespace app cron selector <<< "$schedule"
  echo "Creating schedule for $namespace with selector $selector"
  velero schedule create "${namespace}-${app}" --schedule "${cron}" --selector "${selector}=${app}" \
  --ttl 216h0m0s --include-namespaces "${namespace}" --include-resources '*' \
  --default-volumes-to-fs-backup=false --snapshot-move-data=true 
done
