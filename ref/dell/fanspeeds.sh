ipmitool -I lanplus -H 192.168.101.200 -U fans -P fans raw 0x30 0xce 0x00 0x16 0x05 0x00 0x00 0x00 0x05 0x00 0x01 0x00 0x00
ipmitool -I lanplus -H 192.168.101.200 -U fans -P fans raw 0x30 0x30 0x01 0x00
ipmitool -I lanplus -H 192.168.101.200 -U fans -P fans raw 0x30 0x30 0x02 0xff 0x14