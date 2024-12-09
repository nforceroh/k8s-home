apiVersion: velero.io/v1
kind: Schedule
metadata:
  name: torrent-prowlarr
  namespace: openshift-adp
spec:
  schedule: 30 0 * * *
  template:
    defaultVolumesToRestic: true
    hooks: {}
    includedNamespaces:
      - torrent
    includedResources:
      - '*'
    labelSelector:
      matchLabels:
        app: prowlarr
    metadata: {}
    ttl: 168h0m0s
  useOwnerReferencesInBackup: false