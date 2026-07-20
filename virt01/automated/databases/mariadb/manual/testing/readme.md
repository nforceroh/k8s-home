# MariaDB Kubernetes Backup & Recovery Guide (Cloudflare R2)

This guide details the procedures for executing manual on-demand backup tests, performing database restores, and validating backup health within our Kubernetes cluster using the cloud-native `mariadb-operator`.

---

## 🏗️ 1. Manual On-Demand Backup Test

To trigger an immediate backup snapshot without waiting for the automated Cron schedules (`mariadb-daily-r2-v2` / `mariadb-monthly-r2-v2`), deploy a one-off `Backup` resource that omits the `spec.schedule` configuration block.

### Step 1: Create the Test Manifest
Run the following command to generate the `mariadb-test-now.yaml` file:

```bash
cat <<EOF > mariadb-test-now.yaml
apiVersion: k8s.mariadb.com/v1alpha1
kind: Backup
metadata:
  name: mariadb-manual-test-now
  namespace: databases
spec:
  mariaDbRef:
    name: mariadb
  storage:
    s3:
      bucket: k8s-data  
      prefix: mariadb-backups/manual-test/
      endpoint: c8447e01e7c0018cf456923099f43457.r2.cloudflarestorage.com
      region: auto
      tls:
        enabled: true
      accessKeyIdSecretKeyRef:
        name: r2-backup-secret
        key: access-key-id
      secretAccessKeySecretKeyRef:
        name: r2-backup-secret
        key: secret-access-key
EOF
```

### Step 2: Deploy and Stream Logs
1. **Apply the manifest:**
   ```bash
   kubectl apply -f mariadb-test-now.yaml
   ```
2. **Watch the backup resource phase transition to `Complete`:**
   ```bash
   kubectl get backup mariadb-manual-test-now -n databases -w
   ```
3. **Stream the raw data-dump execution logs:**
   ```bash
   kubectl logs -l app.kubernetes.io/instance=mariadb-manual-test-now -n databases -f
   ```

### Step 3: Cleanup Test Context
Once files appear successfully inside your Cloudflare R2 dashboard under `mariadb-backups/manual-test/`, remove the test object to keep your cluster state clean:
```bash
kubectl delete -f mariadb-test-now.yaml
```

---

## 🔄 2. Data Recovery Procedure & Restore Validation

To recover data or bootstrap tables from an R2 backup, use a **`kind: Restore`** resource. This action should always be verified in an isolated staging environment before attempting on production instances.

### Step 1: Deploy a Fresh Staging Database Target
Generate and apply an empty test instance that references the existing production `mariadb-auth` secret:

```bash
cat <<EOF > mariadb-staging.yaml
apiVersion: k8s.mariadb.com/v1alpha1
kind: MariaDB
metadata:
  name: mariadb-staging
  namespace: databases
spec:
  rootPasswordSecretKeyRef:
    name: mariadb-auth
    key: mariadb-password
  storage:
    size: 10Gi
    storageClassName: openebs-zfspv-lz4
  replicas: 1
  myCnf: |
    [mariadb]
    bind-address=*
    default_storage_engine=InnoDB
    binlog_format=row
    innodb_autoinc_lock_mode=2
    innodb_buffer_pool_size=800M
    max_allowed_packet=256M
    [client]
    port=3306
EOF

kubectl apply -f mariadb-staging.yaml
kubectl get mariadb mariadb-staging -n databases -w
```

### Step 2: Create the Restore Manifest
Save the configuration below as `mariadb-restore.yaml`. The `backupRef` points directly to the on-demand test metadata wrapper created in Section 1:

```bash
cat <<EOF > mariadb-restore.yaml
apiVersion: k8s.mariadb.com/v1alpha1
kind: Restore
metadata:
  name: mariadb-clone-restore
  namespace: databases
spec:
  mariaDbRef:
    name: mariadb-staging # Target staging instance
  backupRef:
    name: mariadb-manual-test-now # Source snapshot definition
EOF
```

### Step 3: Apply and Monitor the Restore Process
1. **Deploy the recovery action:**
   ```bash
   kubectl apply -f mariadb-restore.yaml
   ```
2. **Track the restore lifecycle phase (Wait for `True` / `Success`):**
   ```bash
   kubectl get restore mariadb-clone-restore -n databases -w
   ```

### Step 4: Run Data Integrity & Row Count Verification
Since production containers are stripped of CLI tools, use a temporary network client pod to query table structures.

1. **Query Production Footprint:**
   ```bash
   kubectl run mariadb-client-prod --rm -it --restart=Never --image=bitnami/mariadb -n databases \
     --env="MYSQL_PWD=\$(kubectl get secret mariadb-auth -n databases -o jsonpath='{.data.mariadb-password}' | base64 --decode)" -- \
     mariadb -h mariadb -u root \
     -e "SELECT table_schema, table_name, table_rows FROM information_schema.tables WHERE table_schema NOT IN ('information_schema', 'performance_schema', 'mysql', 'sys');"
   ```

2. **Query Staging (Restored) Footprint:**
   ```bash
   kubectl run mariadb-client-stage --rm -it --restart=Never --image=bitnami/mariadb -n databases \
     --env="MYSQL_PWD=\$(kubectl get secret mariadb-auth -n databases -o jsonpath='{.data.mariadb-password}' | base64 --decode)" -- \
     mariadb -h mariadb-staging -u root \
     -e "SELECT table_schema, table_name, table_rows FROM information_schema.tables WHERE table_schema NOT IN ('information_schema', 'performance_schema', 'mysql', 'sys');"
   ```

*Compare the row counts (`table_rows`) of critical application areas like `powerdns_ns1.records` and `mail.alias`. They must line up 1:1 with your production baseline metrics from the time the snapshot was captured.*

### Step 5: Clean Up Validation Resources
Once data validation finishes, clean up the testing environment:
```bash
kubectl delete mariadb mariadb-staging -n databases
kubectl delete restore mariadb-clone-restore -n databases
```

---

## 🛡️ 3. Validation and Health Observability

### Cluster Resource Status Validation
Run the following commands to check the operational loops of both automated schedules:
```bash
# Check validation status and next planned run execution times
kubectl get backups -A

# Inspect extended history events or errors
kubectl describe backup mariadb-daily-r2-v2 -n databases
```

### Prometheus / Alertmanager Metrics Validation
If Prometheus scraping is enabled, ensure that metrics are validating successfully via the Prometheus expression browser UI using these queries:

* **Verify Failed Jobs:** `mariadb_operator_backup_status{status="Failed"}` (Should return `0`)
* **Verify Last Completed Snapshot Age:** `time() - mariadb_operator_backup_last_completion_timestamp` (Should be `< 93600` seconds for daily schedules)
