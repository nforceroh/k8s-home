apiVersion: velero.io/v1
kind: Schedule
metadata:
  name: torrent-radarr
  namespace: openshift-adp
spec:
  schedule: 45 0 * * *
  template:
    defaultVolumesToRestic: true
    hooks: {}
    includedNamespaces:
      - torrent
    includedResources:
      - '*'
    labelSelector:
      matchLabels:
        app: radarr
    metadata: {}
    ttl: 168h0m0s
  useOwnerReferencesInBackup: false