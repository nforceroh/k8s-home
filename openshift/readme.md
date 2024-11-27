# add internal cert
```
step ca certificate --san *.apps.kube.nf.lab *.apps.kube.nf.lab wild.apps.kube.nf.lab.crt wild.apps.kube.nf.lab.key --not-after=87000h
oc create configmap custom-ca --from-file=ca-bundle.crt=root_ca.crt -n openshift-config
oc patch proxy/cluster --type=merge --patch='{"spec":{"trustedCA":{"name":"custom-ca"}}}'
oc create secret tls apps-kube-nf-lab --cert wild.apps.kube.nf.lab.crt  --key wild.apps.kube.nf.lab.key  -n openshift-ingress
oc patch ingresscontroller.operator default --type=merge -p '{"spec":{"defaultCertificate": {"name": "apps-kube-nf-lab"}}}' -n openshift-ingress-operator
```

# vm support
- openshift virtualization
- install nmstate operator

# use hostpath provisioner
```
oc create -f hpp4truenas.yaml 
```