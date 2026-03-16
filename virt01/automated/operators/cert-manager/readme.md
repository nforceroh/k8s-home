# Chart information

helm chart location: <https://github.com/cert-manager/cert-manager/tree/master/deploy/charts/cert-manager>


>Deploying the chart

```bash
# Add the Jetstack Helm repository
helm repo add jetstack https://charts.jetstack.io --force-update

# Install the cert-manager helm chart
helm install \
  cert-manager jetstack/cert-manager \
  --namespace cert-manager \
  --create-namespace \
  --version {{RELEASE_VERSION}} \
  --set crds.enabled=true
```


