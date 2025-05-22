
```bash
helm upgrade --install -n gpu-operator --create-namespace gpu-operator .
```

## Verify timeslicing

```bash
kubectl describe node virt01 |egrep "gpu.count|gpu.product|gpu.replicas"
```

