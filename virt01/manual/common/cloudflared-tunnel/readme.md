# https://developers.cloudflare.com/cloudflare-one/connections/connect-networks/

# dns entry muse be manually created
https://developers.cloudflare.com/cloudflare-one/connections/connect-networks/routing-to-tunnel/dns/



# Create sealed secret from  cloudflared tunnel create
```
kubectl create secret generic tunnel-credentials -n common \
 --from-file=credentials.json=$HOME/.cloudflared/f680dab0-f01a-421d-a28a-ac0f21f0388b.json \
 -o yaml --dry-run=client | \
 kubeseal --cert "$HOME/gitdev/k8s-home/k8s-home-secrets/sealed-secrets/nf-lab.crt" \
 --scope cluster-wide -o yaml > ./templates/tunnel-credentials-sealed.yaml
```