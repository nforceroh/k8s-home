# fetch kubeseal
see https://github.com/bitnami-labs/sealed-secrets?tab=readme-ov-file#linux


# Check if you can get the certs
```
kubeseal --fetch-cert --controller-name sealed-secrets --controller-namespace common
```
