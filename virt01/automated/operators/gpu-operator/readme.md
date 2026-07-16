
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

https://www.talos.dev/v1.8/talos-guides/configuration/nvidia-gpu/

https://github.com/NVIDIA/k8s-device-plugin/blob/main/deployments/helm/nvidia-device-plugin/values.yaml

# test SMI
```
kubectl run nvidia-test --restart=Never -ti --rm --image nvcr.io/nvidia/cuda:12.5.0-base-ubuntu22.04  --overrides '{"spec": {"runtimeClassName": "nvidia"}}' nvidia-smi -n gpu-operator
```

```
cat <<EOF | kubectl apply -n ai -f -
apiVersion: v1
kind: Pod
metadata:
  name: gpu-pod
spec:
  restartPolicy: Never
  containers:
    - name: cuda-container
      image: nvcr.io/nvidia/k8s/cuda-sample:vectoradd-cuda12.5.0
      resources:
        limits:
          nvidia.com/gpu: 1 # requesting 1 GPU
  tolerations:
  - key: nvidia.com/gpu
    operator: Exists
    effect: NoSchedule
EOF
```