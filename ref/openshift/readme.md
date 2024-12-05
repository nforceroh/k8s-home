# add internal cert
```
step ca certificate --san *.apps.kube.nf.lab *.apps.kube.nf.lab wild.apps.kube.nf.lab.crt wild.apps.kube.nf.lab.key --not-after=87000h
oc create configmap custom-ca --from-file=ca-bundle.crt=../secretsRaw/openshift/root_ca.crt -n openshift-config
oc patch proxy/cluster --type=merge --patch='{"spec":{"trustedCA":{"name":"custom-ca"}}}'
oc create secret tls apps-kube-nf-lab --cert ../secretsRaw/openshift/wild.apps.kube.nf.lab.crt  --key ../secretsRaw/openshift/wild.apps.kube.nf.lab.key  -n openshift-ingress
oc patch ingresscontroller.operator default --type=merge -p '{"spec":{"defaultCertificate": {"name": "apps-kube-nf-lab"}}}' -n openshift-ingress-operator
```

# setup LVMCluster
```
oc create -f <<EOF
apiVersion: lvm.topolvm.io/v1alpha1
kind: LVMCluster
metadata:
  name: test-lvmcluster
  namespace: openshift-storage
spec:
  storage:
    deviceClasses:
      - deviceSelector:
          paths:
            - /dev/sdb
        fstype: xfs
        name: vg1
        thinPoolConfig:
          chunkSizeCalculationPolicy: Static
          name: thin-pool-1
          overprovisionRatio: 10
          sizePercent: 90
EOF
```

# patch lvm sc
```
oc patch storageclass lvms-vg1 -p '{"metadata": {"annotations": {"storageclass.kubernetes.io/is-default-class": "true"}}}'
```

# vm support
- openshift virtualization
- install nmstate operator

# PCi passthrough
# https://docs.openshift.com/container-platform/4.16/virt/virtual_machines/advanced_vm_management/virt-configuring-pci-passthrough.html#virt-preparing-host-devices-for-pci-passthrough
```
[root@virt01 ~]# lspci -nnv |grep SAS
03:00.0 Serial Attached SCSI controller [0107]: Broadcom / LSI SAS3008 PCI-Express Fusion-MPT SAS-3 [1000:0097] (rev 02)
83:00.0 RAID bus controller [0104]: Broadcom / LSI MegaRAID SAS-3 3008 [Fury] [1000:005f] (rev 02)
```

# change the line to have the dev id in the butane file
```
 options vfio-pci ids=1000:0097
```
# Install butane if needed
```
curl https://mirror.openshift.com/pub/openshift-v4/clients/butane/latest/butane --output butane
```

```
~/butane 100-worker-vfiopci.bu -o 100-worker-vfiopci.yaml
or
~/butane 100-master-vfiopci.bu -o 100-master-vfiopci.yaml
```
# apply config (SNO)
```
oc apply -f 100-master-vfiopci.yaml -f 100-master-iommu.yaml 
```

# apply config (non SNO)
```
oc apply -f 100-worker-vfiopci.yaml -f 100-worker-iommu.yaml 
```
