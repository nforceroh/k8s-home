# PostgreSQL credentials

This cluster is named `pg-db` and runs in namespace `databases`.

CloudNativePG creates Kubernetes Secrets with credentials.

## Password create using sealed secrets

Go to https://github.com/nforceroh/k8s-home-secrets for instructions.

## 1) Find the generated secrets

```bash
kubectl -n databases get secret | grep pg-db
```

Typical secrets are:
- `pg-db-app` (recommended app user)
- `pg-db-superuser` (postgres superuser, because `enableSuperuserAccess: true`)

## 2) Get the app password (recommended)

```bash
kubectl -n databases get secret pg-db-app -o jsonpath='{.data.password}' | base64 -d; echo
```

Optional: get all app connection fields from the same secret:

```bash
kubectl -n databases get secret pg-db-app -o jsonpath='{.data.username}' | base64 -d; echo
kubectl -n databases get secret pg-db-app -o jsonpath='{.data.dbname}' | base64 -d; echo
kubectl -n databases get secret pg-db-app -o jsonpath='{.data.host}' | base64 -d; echo
kubectl -n databases get secret pg-db-app -o jsonpath='{.data.port}' | base64 -d; echo
```

## 3) Get the superuser password (if needed)

```bash
kubectl -n databases get secret pg-db-superuser -o jsonpath='{.data.password}' | base64 -d; echo
```

## 4) Build a DSN/connection string

```bash
PGUSER=$(kubectl -n databases get secret pg-db-app -o jsonpath='{.data.username}' | base64 -d)
PGPASSWORD=$(kubectl -n databases get secret pg-db-app -o jsonpath='{.data.password}' | base64 -d)
PGHOST=$(kubectl -n databases get secret pg-db-app -o jsonpath='{.data.host}' | base64 -d)
PGPORT=$(kubectl -n databases get secret pg-db-app -o jsonpath='{.data.port}' | base64 -d)
PGDATABASE=$(kubectl -n databases get secret pg-db-app -o jsonpath='{.data.dbname}' | base64 -d)

echo "postgresql://${PGUSER}:${PGPASSWORD}@${PGHOST}:${PGPORT}/${PGDATABASE}?sslmode=require"
```

If your app does not support TLS yet, try `sslmode=disable` first and then switch to TLS once certs are configured.

## 5) Set a static password

Yes, you can use static passwords.

### Option A (best for new clusters): declare secrets and reference them in the cluster spec

1. Create the secrets first:

```bash
kubectl -n databases create secret generic pg-db-app \
  --from-literal=username=app \
  --from-literal=password='REPLACE_WITH_STRONG_PASSWORD'

kubectl -n databases create secret generic pg-db-superuser \
  --from-literal=username=postgres \
  --from-literal=password='REPLACE_WITH_STRONG_PASSWORD'
```

2. Update `cluster.yaml` to reference those secrets:

```yaml
apiVersion: postgresql.cnpg.io/v1
kind: Cluster
metadata:
  name: pg-db
spec:
  instances: 1
  imageName: ghcr.io/cloudnative-pg/postgresql:16.2
  storage:
    size: 10Gi

  enableSuperuserAccess: true
  superuserSecret:
    name: pg-db-superuser

  bootstrap:
    initdb:
      database: app
      owner: app
      secret:
        name: pg-db-app
```

3. Apply the updated manifest.

Important: `bootstrap.initdb` is only used during initial cluster creation.
If the cluster already exists, use Option B.

### Option B (for this existing cluster): rotate DB password and sync the Kubernetes Secret

Set a new app-user password:

```bash
NEW_APP_PASSWORD='REPLACE_WITH_STRONG_PASSWORD'
APP_USER=$(kubectl -n databases get secret pg-db-app -o jsonpath='{.data.username}' | base64 -d)
PG_POD=$(kubectl -n databases get pod -l cnpg.io/cluster=pg-db -o jsonpath='{.items[0].metadata.name}')

kubectl -n databases exec "$PG_POD" -- psql -U postgres -d postgres \
  -c "ALTER ROLE ${APP_USER} WITH PASSWORD '${NEW_APP_PASSWORD}';"

kubectl -n databases patch secret pg-db-app --type=merge \
  -p "{\"stringData\":{\"password\":\"${NEW_APP_PASSWORD}\"}}"
```

Set a new superuser password:

```bash
NEW_SUPERUSER_PASSWORD='REPLACE_WITH_STRONG_PASSWORD'
PG_POD=$(kubectl -n databases get pod -l cnpg.io/cluster=pg-db -o jsonpath='{.items[0].metadata.name}')

kubectl -n databases exec "$PG_POD" -- psql -U postgres -d postgres \
  -c "ALTER ROLE postgres WITH PASSWORD '${NEW_SUPERUSER_PASSWORD}';"

kubectl -n databases patch secret pg-db-superuser --type=merge \
  -p "{\"stringData\":{\"password\":\"${NEW_SUPERUSER_PASSWORD}\"}}"
```
