# Add KVM
https://www.server-world.info/en/note?os=Ubuntu_24.04&p=kvm&f=1
```
sudo  root@dlp:~# apt -y install qemu-kvm libvirt-daemon-system libvirt-daemon virtinst bridge-utils libosinfo-bin
```

# get HOAS
```
mkdir -p /var/kvm/images 
wget https://github.com/home-assistant/operating-system/releases/download/14.0/haos_ova-14.0.qcow2.xz -O /var/kvm/images/haos_ova-14.0.qcow2.xz
cd /var/kvm/images 
xz -d haos_ova-14.0.qcow2.xz 
```

```
virt-install --name haos --description "Home Assistant OS" \
--os-variant=generic \
--ram=4096 --vcpus=2 \
--network bridge=br1000 \
--disk /var/kvm/images/haos_ova-14.0.qcow2,bus=scsi \
--controller type=scsi,model=virtio-scsi --import --graphics none --boot uefi
```

```
virsh attach-interface --type bridge --source br1990 --model virtio haos --persistent
virsh attach-interface --type bridge --source br1400 --model virtio haos --persistent
```

virsh autostart Domain