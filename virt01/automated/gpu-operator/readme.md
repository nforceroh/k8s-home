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