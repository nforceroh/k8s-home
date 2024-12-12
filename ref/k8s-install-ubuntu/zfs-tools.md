```
cd /tmp
wget https://github.com/openzfs/zfs/archive/refs/heads/master.zip
unzip master.zip
```

```
for f in `ls zfs-master/etc/systemd/system/*`; do echo "Moving $f"; cp $f /etc/systemd/system/;done
```