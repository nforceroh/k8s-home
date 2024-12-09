apiVersion: velero.io/v1
kind: Schedule
metadata:
  name: mail-rspamd
  namespace: openshift-adp
spec:
  schedule: 0 20 * * *
  template:
    defaultVolumesToRestic: true
    hooks: {}
    includedNamespaces:
      - mail
    includedResources:
      - '*'
    labelSelector:
      matchLabels:
        app: rspamd
    metadata: {}
    ttl: 168h0m0s
  useOwnerReferencesInBackup: false