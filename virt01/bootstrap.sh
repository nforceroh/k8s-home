#!/bin/bash
set -e

echo "=== Bootstrap ArgoCD on virt01 ==="

# Check helm
if ! command -v helm &> /dev/null; then
    echo "Installing helm..."
    curl https://raw.githubusercontent.com/helm/helm/main/scripts/get-helm-3 | bash
fi

# Add helm repos
echo "=== Adding Helm repos ==="
helm repo add argo https://argoproj.github.io/argo-helm 2>/dev/null || true
helm repo add prometheus-community https://prometheus-community.github.io/helm-charts 2>/dev/null || true
helm repo update

# Create required namespaces
echo "=== Creating namespaces ==="
kubectl create namespace argocd 2>/dev/null || true
kubectl create namespace monitoring 2>/dev/null || true

# Install Prometheus CRDs (needed for ServiceMonitor/PrometheusRule)
echo "=== Installing Prometheus CRDs ==="
kubectl apply --server-side -f https://github.com/prometheus-operator/prometheus-operator/releases/latest/download/bundle.yaml
sleep 5

# Install ArgoCD CRDs first with correct Helm labels
echo "=== Installing ArgoCD CRDs ==="
kubectl apply --server-side -f https://raw.githubusercontent.com/argoproj/argo-cd/stable/manifests/crds/application-crd.yaml
kubectl apply --server-side -f https://raw.githubusercontent.com/argoproj/argo-cd/stable/manifests/crds/appproject-crd.yaml
kubectl apply --server-side -f https://raw.githubusercontent.com/argoproj/argo-cd/stable/manifests/crds/applicationset-crd.yaml
sleep 5

# Label CRDs for Helm adoption
echo "=== Labeling CRDs for Helm ==="
for crd in applications.argoproj.io appprojects.argoproj.io applicationsets.argoproj.io; do
    kubectl label crd $crd app.kubernetes.io/managed-by=Helm --overwrite 2>/dev/null || true
    kubectl annotate crd $crd meta.helm.sh/release-name=argocd --overwrite 2>/dev/null || true
    kubectl annotate crd $crd meta.helm.sh/release-namespace=argocd --overwrite 2>/dev/null || true
done

# Update helm dependencies
echo "=== Updating Helm dependencies ==="
helm dependency update argocd

# Install ArgoCD
echo "=== Installing ArgoCD ==="
helm upgrade --install argocd ./argocd \
    -n argocd \
    --create-namespace \
    --wait \
    --timeout 300s \
    --values argocd/values.yaml 

echo "=== ArgoCD installed successfully ==="
echo "=== Waiting for pods to be ready ==="
kubectl wait --for=condition=ready pod -l app.kubernetes.io/name=argocd-server -n argocd --timeout=120s

echo "=== Port-forwarding ArgoCD to localhost:8080 ==="
kubectl port-forward -n argocd svc/argocd-server 8080:80 &

echo ""
echo "=== Done! ==="
echo "ArgoCD is available at http://localhost:8080"
echo "Username: admin"
echo "Password is set in your values.yaml"