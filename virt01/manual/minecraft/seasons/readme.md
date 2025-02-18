# Install
```
helm upgrade --install seasons . -n minecraft --create-namespace -f values.yaml 
```

# DNS setup
https://www.name.com/support/articles/205188518-setting-up-dns-for-a-minecraft-server


```
SRV NAME: mc2
SERVICE: _minecraft
PROTOCOL: tcp
PRIO: 1
WEIGHT: 1
PORT: 25566
TARGET: ipv4.nforcer.com
TTL: auto
```
