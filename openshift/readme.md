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

