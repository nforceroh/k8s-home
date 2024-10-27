
```
helm repo add democratic-csi https://democratic-csi.github.io/charts/
helm repo update
helm search repo democratic-csi/
```
# Install snapshot crd
```
kubectl apply -f https://raw.githubusercontent.com/kubernetes-csi/external-snapshotter/refs/heads/master/client/config/crd/snapshot.storage.k8s.io_volumesnapshotclasses.yaml
kubectl apply -f https://raw.githubusercontent.com/kubernetes-csi/external-snapshotter/refs/heads/master/client/config/crd/snapshot.storage.k8s.io_volumesnapshotcontents.yaml
kubectl apply -f https://raw.githubusercontent.com/kubernetes-csi/external-snapshotter/refs/heads/master/client/config/crd/snapshot.storage.k8s.io_volumesnapshots.yaml
```
# Install snapshotter
```

helm upgrade --install --values values.yaml -n csi --create-namespace snapshot-controller democratic-csi/snapshot-controller

```

# install iscsi
```
helm upgrade --install --values values.yaml -n csi --create-namespace zfs-iscsi democratic-csi/democratic-csi
```


# uninstall
```
helm delete --namespace democratic-csi zfs-iscsi
helm delete --namespace democratic-csi zfs-nfs
```
