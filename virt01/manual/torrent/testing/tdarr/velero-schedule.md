apiVersion: velero.io/v1
kind: Schedule
metadata:
  name: torrent-tdarr
  namespace: openshift-adp
spec:
  schedule: 55 0 * * *
  template:
    defaultVolumesToRestic: true
    hooks: {}
    includedNamespaces:
      - torrent
    includedResources:
      - '*'
    labelSelector:
      matchLabels:
        app: tdarr
    metadata: {}
    ttl: 168h0m0s
  useOwnerReferencesInBackup: false