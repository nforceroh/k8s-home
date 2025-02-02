# https://kubebyexample.com/learning-paths/kubevirt-fundamentals/guided-exercise-installing-kubevirt

## Grab the latest version of KubeVirt

```bash
KUBEVIRT_VERSION=$(curl -s https://api.github.com/repos/kubevirt/kubevirt/releases/latest | awk -F '[ \t":]+' '/tag_name/ {print $3}')
```

## insert that version into Chart.yaml

```bash
echo $KUBEVIRT_VERSION
sed -e "s/^appVersion: .*$/appVersion: \"$KUBEVIRT_VERSION\"\n/g" Chart.yaml
```

```bash
wget https://github.com/kubevirt/kubevirt/releases/download/${KUBEVIRT_VERSION}/kubevirt-operator.yaml -O templates/kubevirt-operator.yaml
wget https://github.com/kubevirt/kubevirt/releases/download/${KUBEVIRT_VERSION}/kubevirt-cr.yaml -O templates/kubevirt-cr.yaml
```

## install virtctl
```bash
curl -Lo virtctl https://github.com/kubevirt/kubevirt/releases/download/${KUBEVIRT_VERSION}/virtctl-${KUBEVIRT_VERSION}-linux-amd64
sudo install -m 0755 -o root -g root virtctl /usr/local/bin/virtctl
rm virtctl
```

```bash
kubectl create -f https://github.com/kubevirt/kubevirt/releases/download/${KUBEVIRT_VERSION}/kubevirt-operator.yaml
kubectl create -f https://github.com/kubevirt/kubevirt/releases/download/${KUBEVIRT_VERSION}/kubevirt-cr.yaml
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

