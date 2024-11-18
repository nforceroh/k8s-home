```
for backup in `velero get backups|grep ns|grep Completed|awk '{print $1}'`; do
  velero restore create --from-backup ${backup} --restore-volumes=true
done