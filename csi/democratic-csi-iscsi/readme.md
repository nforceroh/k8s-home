
```
helm repo add democratic-csi https://democratic-csi.github.io/charts/
helm repo update
helm search repo democratic-csi/
```

# install iscsi
```
helm upgrade \
--install \
--values truenas-iscsi.yaml \
--namespace democratic-csi \
--create-namespace \
zfs-iscsi democratic-csi/democratic-csi
```

# install nfs
```
helm upgrade \
--install \
--values truenas-nfs.yaml \
--namespace democratic-csi \
zfs-nfs democratic-csi/democratic-csi
```
# Install snapshotter
```

helm upgrade --install --namespace democratic-csi --create-namespace snapshot-controller democratic-csi/snapshot-controller

```

# uninstall
```
helm delete --namespace democratic-csi zfs-iscsi
helm delete --namespace democratic-csi zfs-nfs
```