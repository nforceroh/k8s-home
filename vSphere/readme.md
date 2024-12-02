# Enable pci passthrough for gpu
https://docs.vmware.com/en/VMware-Edge-Compute-Stack/3.0/ecs-enterprise-edge-ref-arch/GUID-412AD9B3-6B9B-4BE0-B833-9205ACBCF956.html


# add to VM
```
pciPassthru.use64bitMMIO="TRUE"
pciPassthru.64bitMMIOSizeGB = "64"

```