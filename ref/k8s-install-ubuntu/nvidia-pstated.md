# nvidia-pstated

## ref
https://github.com/sasha0552/nvidia-pstated

```bash
wget https://github.com/sasha0552/nvidia-pstated/releases/download/v1.0.7/nvidia-pstated -o /tmp/nvidia-pstated
sudo install -m 755 -o root -g root /tmp/nvidia-pstated /usr/local/bin
rm -f /tmp/nvidia-pstated
```

```bash
cat <<EOF > /tmp/nvidia-pstated.service
[Unit]
Description=A daemon that automatically manages the performance states of NVIDIA GPUs
StartLimitInterval=0

[Service]
DynamicUser=yes
ExecStart=/usr/local/bin/nvidia-pstated
Restart=on-failure
RestartSec=1s

[Install]
WantedBy=multi-user.target
EOF

sudo cp /tmp/nvidia-pstated.service /etc/systemd/system/nvidia-pstated.service
sudo systemctl daemon-reload
sudo systemctl enable --now nvidia-pstated.service
```
