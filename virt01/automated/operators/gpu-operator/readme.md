
## Reference
https://docs.nvidia.com/datacenter/cloud-native/gpu-operator/latest/gpu-sharing.html#time-slicing-verify

https://www.redhat.com/en/blog/sharing-caring-how-make-most-your-gpus-part-1-time-slicing

https://github.com/NVIDIA/gpu-operator/blob/main/deployments/gpu-operator/values.yaml


```bash
helm upgrade --install -n gpu-operator --create-namespace gpu-operator .
```

```bash
oc label node virt01 nvidia.com/device-plugin.config=Tesla-P40
```

## Verify timeslicing


```bash
kubectl describe node virt01 |egrep "gpu.count|gpu.product|gpu.replicas|device-plugin.config|gpu.product"
                    nvidia.com/device-plugin.config=Tesla-P40
                    nvidia.com/gpu.count=1
                    nvidia.com/gpu.product=Tesla-P40-SHARED
                    nvidia.com/gpu.replicas=8
```

