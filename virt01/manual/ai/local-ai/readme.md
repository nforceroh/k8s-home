# Chart information

helm chart location: <https://go-skynet.github.io/helm-charts/>


>Deploying the chart

```bash
helm repo add go-skynet https://go-skynet.github.io/helm-charts/
helm repo update

helm dependency build

helm upgrade --install localai . --namespace ai  -f values.yaml
```


