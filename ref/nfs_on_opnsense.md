# 📑 Engineering Blueprint: Persistent Kubernetes NFS Storage on OPNsense 26.7

This document provides a comprehensive technical guide for configuring a bare-metal Dell PowerEdge R330 firewall running **OPNsense 26.7-amd64** to serve as a high-performance, fault-tolerant network storage backend for a single-node Kubernetes cluster (`virt01`).

---

## 🎛️ 1. ZFS Storage Array Initialization
The storage array consists of four (4) 8TB HP enterprise SAS hard drives (`da0` through `da3`) managed via a Dell PERC H330 controller in pass-through (HBA) mode.

Because these enterprise drives utilize an Advanced Format physical platter layout (`stripesize 4096`), the ZFS storage pool must be forcefully aligned to **4K boundaries** using the `ashift=12` parameter to eliminate write-amplification bottlenecks.

```bash
# Destroy any existing temporary test pools
zpool destroy k8s-pool

# Create the optimized 4-drive 4K-aligned RAIDZ1 pool (~24TB usable)
zpool create -f -o ashift=12 k8s-pool raidz1 /dev/da0 /dev/da1 /dev/da2 /dev/da3

# Provision the target dataset partition for Kubernetes storage volumes
zfs create k8s-pool/k8s-volumes

# Enable native transparent LZ4 compression to optimize I/O performance and space
zfs set compression=lz4 k8s-pool/k8s-volumes

# Apply broad read/write execution permissions for cluster drivers
chmod 777 /k8s-pool/k8s-volumes
```

---

## 🔏 2. NFS Permissions & Export Configuration
To allow the Kubernetes CSI driver (`nfs-subdir-external-provisioner`) to dynamically provision and manage underlying directories, root-squashing must be explicitly bypassed.

Edit the configuration file on the OPNsense terminal:
```bash
ee /etc/exports
```

Paste your exact network boundary permissions string (substitute with your targeted cluster VLAN subnet mask):
```text
/k8s-pool/k8s-volumes -alldirs -maproot=root -network 10.0.0.0 -mask 255.255.255.0
```

---

## 🚀 3. OPNsense 26.7 Persistent Boot Automation Loop
OPNsense 26.7 deliberately sweeps and clears custom system configuration paths (like `/etc/rc.conf.d/` and `/etc/rc.local`) during its boot cycle to harden the firewall. Furthermore, it explicitly leaves secondary data pools unimported on system startup.

To bypass this restriction, the automation loop must be placed inside the official OPNsense **`rc.syshook.d/start`** directory. This script forces the machine to wait for the storage interfaces to stabilize, imports the ZFS disk array, and spins up the storage daemons directly.

Create the persistent startup orchestration file:
```bash
ee /usr/local/etc/rc.syshook.d/start/90-k8s-nfs-boot
```

Paste this production code block entirely into the workspace:
```bash
#!/bin/sh

# 1. Force a pause loop until the local 10.0.0.1 VLAN gateway interface is completely online
until ping -c 1 -t 1 10.0.0.1 >/dev/null 2>&1; do
    sleep 2
done

# 2. Force OPNsense to import the 4-drive data array if left unimported by the OS bootloader
if ! zpool list | grep -q "k8s-pool"; then
    echo "k8s-pool not found in active memory. Forcing ZFS pool import..." >> /var/log/k8s-nfs-boot.log
    zpool import -f -a
fi

# 3. Force a confirmation verification check that the storage directory path is active
until [ -d "/k8s-pool/k8s-volumes" ]; do
    echo "Waiting for ZFS storage dataset pool to mount..." >> /var/log/k8s-nfs-boot.log
    sleep 2
done

# 4. Inject volatile configuration variables straight into the active runtime memory tables
sysrc -q rpcbind_enable="YES"
sysrc -q mountd_enable="YES"
sysrc -q mountd_flags="-r"
sysrc -q nfs_server_enable="YES"
sysrc -q nfsv4_server_enable="YES"

# 5. Direct hardware execution block bypassing standard configuration registry masks
/usr/sbin/rpcbind -W
/usr/sbin/mountd -r /etc/exports
/usr/sbin/nfsd -n 4

# 6. Force a final hot-reload to push the exports table live on active kernel maps
/usr/sbin/mountd -r
echo "$(date): NFS Storage Backbone successfully initialized!" >> /var/log/k8s-nfs-boot.log
```

Apply executable permissions so the OPNsense bootloader loads it:
```bash
chmod +x /usr/local/etc/rc.syshook.d/start/90-k8s-nfs-boot
```

---

## 🔍 4. Cluster Verification Playbook

### From the OPNsense Firewall:
Verify that your ZFS dataset has been successfully imported and mapped:
```bash
zpool status k8s-pool
```

Verify that the NFS server is actively broadcasting your path over your network link:
```bash
showmount -e
```
*Expected Output:*
```text
Exports list on localhost:
/k8s-pool/k8s-volumes          10.0.0.0
```

### From the Kubernetes Cluster Node (`virt01`):
Verify that the node can see the firewall's storage share over the VLAN bridge network interface:
```bash
showmount -e 10.0.0.1
```
*Expected Output:*
```text
Export list for 10.0.0.1:
/k8s-pool/k8s-volumes          10.0.0.0
```

Verify that all of your cluster's Persistent Volume Claims (PVCs) have automatically locked into a working state:
```bash
kubectl get pvc -A
```
*The status column will proudly register every single storage allocation container path as **`Bound`**.*
