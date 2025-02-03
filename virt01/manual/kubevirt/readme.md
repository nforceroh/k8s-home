# https://kubebyexample.com/learning-paths/kubevirt-fundamentals/guided-exercise-installing-kubevirt

## Grab the latest version of KubeVirt

```bash
KUBEVIRT_VERSION=$(curl -s https://api.github.com/repos/kubevirt/kubevirt/releases/latest | awk -F '[ \t":]+' '/tag_name/ {print $3}')

echo $KUBEVIRT_VERSION
```

```bash
kubectl create -f https://github.com/kubevirt/kubevirt/releases/download/${KUBEVIRT_VERSION}/kubevirt-operator.yaml
kubectl create -f https://github.com/kubevirt/kubevirt/releases/download/${KUBEVIRT_VERSION}/kubevirt-cr.yaml
```

## Install cdi
```bash
export VERSION=$(curl -Ls https://github.com/kubevirt/containerized-data-importer/releases/latest | grep -m 1 -o "v[0-9]\.[0-9]*\.[0-9]*")

echo $VERSION
```

## install virtctl
```bash
curl -Lo virtctl https://github.com/kubevirt/kubevirt/releases/download/${KUBEVIRT_VERSION}/virtctl-${KUBEVIRT_VERSION}-linux-amd64
sudo install -m 0755 -o root -g root virtctl /usr/local/bin/virtctl
rm virtctl
```

## Install cdi
```bash
export CDI_VERSION=$(curl -Ls https://github.com/kubevirt/containerized-data-importer/releases/latest | grep -m 1 -o "v[0-9]\.[0-9]*\.[0-9]*")
echo $CDI_VERSION
kubectl create -f https://github.com/kubevirt/containerized-data-importer/releases/download/${CDI_VERSION}/cdi-operator.yaml
kubectl create -f https://github.com/kubevirt/containerized-data-importer/releases/download/${CDI_VERSION}/cdi-cr.yaml
```


## install kubevirt manager
```bash
kubectl apply -f https://raw.githubusercontent.com/kubevirt-manager/kubevirt-manager/main/kubernetes/bundled.yaml
kubectl apply -f https://raw.githubusercontent.com/kubevirt-manager/kubevirt-manager/refs/heads/main/kubernetes/prometheus-config.yaml
```

## kubevirt-manager ingress
```bash
kubectl apply -f ../kubevirt-manager/templates/ingress.yaml
```

