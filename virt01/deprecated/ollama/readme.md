# Chart information

helm chart location: <https://github.com/otwld/ollama-helm>


>Deploying the chart

```bash
helm repo add ollama-helm https://otwld.github.io/ollama-helm/
helm repo update
#helm upgrade --install ollama ollama-helm/ollama --namespace ai --values ollama_values.yml
# As a subchart
helm upgrade --install ollama . --namespace ai 
```


