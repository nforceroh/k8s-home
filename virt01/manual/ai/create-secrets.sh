# Create secrets for each agent
# Replace YOUR_OPENROUTER_API_KEY with your actual key
#
# For future agents: Use ~/repositories/k8s-home-secrets for creating sealedsecrets
# Example workflow:
#   1. Create a regular secret in a temp namespace
#   2. Use kubeseal to create a SealedSecret
#   3. Commit the SealedSecret to this repo
#   4. Apply with kubectl apply -f sealedsecret.yaml
#
# See: https://github.com/bitnami-labs/sealed-secrets
#
# Example for new agents:
#   kubectl create secret generic newagent-secrets \
#     --namespace=newagent \
#     --from-literal=openrouter-api-key=YOUR_OPENROUTER_API_KEY \
#     --dry-run=client -o json | \
#     kubeseal --format=yaml > ~/repositories/k8s-home-secrets/newagent-sealed-secret.yaml

# KubeOpenCode secrets
kubectl create secret generic kubeopencode-secrets \
  --namespace=kubeopencode \
  --from-literal=openrouter-api-key=YOUR_OPENROUTER_API_KEY

# Hermes secrets
kubectl create secret generic hermes-secrets \
  --namespace=hermes \
  --from-literal=openrouter-api-key=YOUR_OPENROUTER_API_KEY \
  --from-literal=hass-token=YOUR_HASS_TOKEN

# OpenCode secrets
kubectl create secret generic opencode-secrets \
  --namespace=opencode \
  --from-literal=openrouter-api-key=YOUR_OPENROUTER_API_KEY \
  --from-literal=github-token=YOUR_GITHUB_TOKEN

# KubeOpenCode kubeconfig (if running inside cluster)
kubectl create secret generic kubeopencode-kubeconfig \
  --namespace=kubeopencode \
  --from-file=config=/home/sylvain/.kube/config