apiVersion: velero.io/v1
kind: Schedule
metadata:
  name: minecraft-mc2
  namespace: openshift-adp
spec:
  schedule: 0 11 * * *
  template:
    defaultVolumesToRestic: true
    hooks: {}
    includedNamespaces:
      - minecraft
    includedResources:
      - '*'
    labelSelector:
      matchLabels:
        app: mc2
    metadata: {}
    ttl: 168h0m0s
  useOwnerReferencesInBackup: false