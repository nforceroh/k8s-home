https://github.com/otwld/ollama-helm

```
helm repo add ollama-helm https://otwld.github.io/ollama-helm/
helm repo update
#helm upgrade --install ollama ollama-helm/ollama --namespace ai --values ollama_values.yml
# As a subchart
helm upgrade --install ollama . --namespace ai 
```


