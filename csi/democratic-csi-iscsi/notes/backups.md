```
for ns in `kubectl get pvc -A|awk '{print $1}'|grep -v NAMESPACE|sort -u`; do
  velero create backup ns-pvc-${ns}  --include-namespaces ${ns} --include-resources '*' --default-volumes-to-fs-backup --storage-location idrive
done