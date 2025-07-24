# Nvidia and P40

Reference:
<https://www.jimangel.io/posts/nvidia-rtx-gpu-kubernetes-setup/>


## Delete all the old drivers

```bash
sudo apt-get purge '^nvidia.*' 'libnvidia.*' 'linux-objects-nvidia.*' 'linux-signatures-nvidia.*' 'xserver-xorg-video-nvidia.*' -y
sudo reboot
```

## Check is HW sees card

```bash
sudo lspci|grep NVI
82:00.0 3D controller: NVIDIA Corporation GP102GL [Tesla P40] (rev a1)
```

## install nvidia drivers

```bash
# List current driver version
sudo ubuntu-drivers list --gpgpu
```

## Confirm the version that supports P40

https://docs.nvidia.com/datacenter/tesla/tesla-release-notes-575-57-08/index.html#hardware-software-support

Confirmed 575 supports P40 as of 7/24/2025

```bash
sudo ubuntu-drivers install nvidia:575-server
sudo apt install nvidia-utils-575-server
sudo apt-get install -y nvidia-container-toolkit nvidia-container-toolkit-base libnvidia-container-tools libnvidia-container1
sudo reboot
```

## Configuring containerd (for Kubernetes)

Configure the container runtime by using the nvidia-ctk command:

```bash
sudo nvidia-ctk runtime configure --runtime=containerd
```

The nvidia-ctk command modifies the /etc/containerd/config.toml file on the host. The file is updated so that containerd can use the NVIDIA Container Runtime.
Restart containerd:

```bash
sudo systemctl restart containerd
```

## If using CRI-O

Configure the container runtime by using the nvidia-ctk command:

```bash
sudo nvidia-ctk runtime configure --runtime=crio
```

The nvidia-ctk command modifies the /etc/crio/crio.conf file on the host. The file is updated so that CRI-O can use the NVIDIA Container Runtime.

```bash
sudo systemctl restart crio
```

## Verify

```bash
# nvidia-smi 
Thu Jul 24 16:25:49 2025       
+-----------------------------------------------------------------------------------------+
| NVIDIA-SMI 575.64.03              Driver Version: 575.64.03      CUDA Version: 12.9     |
|-----------------------------------------+------------------------+----------------------+
| GPU  Name                 Persistence-M | Bus-Id          Disp.A | Volatile Uncorr. ECC |
| Fan  Temp   Perf          Pwr:Usage/Cap |           Memory-Usage | GPU-Util  Compute M. |
|                                         |                        |               MIG M. |
|=========================================+========================+======================|
|   0  Tesla P40                      Off |   00000000:82:00.0 Off |                  Off |
| N/A   34C    P8             10W /  250W |       0MiB /  24576MiB |      0%      Default |
|                                         |                        |                  N/A |
+-----------------------------------------+------------------------+----------------------+
                                                                                         
+-----------------------------------------------------------------------------------------+
| Processes:                                                                              |
|  GPU   GI   CI              PID   Type   Process name                        GPU Memory |
|        ID   ID                                                               Usage      |
|=========================================================================================|
|  No running processes found                                                             |
+-----------------------------------------------------------------------------------------+
```