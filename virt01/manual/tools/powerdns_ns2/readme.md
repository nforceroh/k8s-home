# Deploy ns2 to k3s, ns1 is on mini pc



cat <<EOF >/tmp/domains
int.nforcer.com
okd.nf.com
ocp.nf.com
v1000.nf.com
v1001.nforcer.com
v999.nforcer.com
v101.nforcer.com
0.0.10.in-addr.arpa
0.1.10.in-addr.arpa
0.2.10.in-addr.arpa
0.3.10.in-addr.arpa
99.0.10.in-addr.arpa
101.168.192.in-addr.arpa
252.168.192.in-addr.arpa
253.168.192.in-addr.arpa
254.168.192.in-addr.arpa
1.0.1.0.1.1.3.c.0.7.4.0.1.0.0.2.ip6.arpa
9.9.9.0.1.1.3.c.0.7.4.0.1.0.0.2.ip6.arpa
0.0.0.1.1.1.3.c.0.7.4.0.1.0.0.2.ip6.arpa
1.0.0.1.1.1.3.c.0.7.4.0.1.0.0.2.ip6.arpa
2.0.0.1.1.1.3.c.0.7.4.0.1.0.0.2.ip6.arpa
3.0.0.1.1.1.3.c.0.7.4.0.1.0.0.2.ip6.arpa
4.0.0.1.1.1.3.c.0.7.4.0.1.0.0.2.ip6.arpa
EOF



DOMAIN="nf.lab"
for p in tanzu okd ocp v101 v999 v1000 v1001 v1002 v1003
do 
 DOMAIN="${p}.nf.lab"
 pdnsutil create-zone ${DOMAIN} ns1.nf.lab.
 pdnsutil add-record ${DOMAIN} @ NS ns2.nf.lab.
 pdnsutil set-kind ${DOMAIN} primary
 pdnsutil set-meta ${DOMAIN} ALLOW-AXFR-FROM AUTO-NS 10.0.0.3
 pdnsutil set-meta ${DOMAIN} ALSO-NOTIFY 10.0.0.3
 pdnsutil set-meta ${DOMAIN} SOA-EDIT-DNSUPDATE DEFAULT 
 pdnsutil set-meta ${DOMAIN} SOA-EDIT-API DEFAULT  
 pdnsutil set-meta ${DOMAIN} SOA-EDIT INCEPTION-INCREMENT
 pdnsutil set-meta ${DOMAIN} TSIG-ALLOW-DNSUPDATE rndc-key
 pdnsutil set-meta ${DOMAIN} ALLOW-DNSUPDATE-FROM 10.0.0.0/8 192.168.0.0/16
done

DOMAIN="nf.lab"
pdnsutil create-zone ${DOMAIN} ns1.nf.lab.
pdnsutil activate-tsig-key ${DOMAIN} rndc-key master
pdnsutil set-meta ${DOMAIN} ALLOW-AXFR-FROM AUTO-NS 10.0.0.2 10.0.0.3
pdnsutil set-meta ${DOMAIN} SOA-EDIT-DNSUPDATE DEFAULT 
pdnsutil set-meta ${DOMAIN} SOA-EDIT-API DEFAULT  
pdnsutil set-meta ${DOMAIN} SOA-EDIT DEFAULT  
pdnsutil set-meta ${DOMAIN} TSIG-ALLOW-DNSUPDATE rndc-key
pdnsutil set-meta ${DOMAIN} ALLOW-DNSUPDATE-FROM 10.0.0.0/8 192.168.0.0/16
pdnsutil add-record ${DOMAIN} @ CNAME 300 nf.lab.
pdnsutil add-record ${DOMAIN} ns1 A 10.0.0.2
pdnsutil add-record ${DOMAIN} ns2 A 10.0.0.3
pdnsutil add-record ${DOMAIN} ca A 10.0.0.2
pdnsutil add-record ${DOMAIN} vcenter A 192.168.101.10
pdnsutil add-record ${DOMAIN} nas01 A 192.168.101.100
pdnsutil add-record ${DOMAIN} esx01 A 192.168.101.101
pdnsutil add-record ${DOMAIN} esx02 A 192.168.101.102
pdnsutil add-record ${DOMAIN} esx03 A 192.168.101.103
pdnsutil add-record ${DOMAIN} esx04 A 192.168.101.104
pdnsutil add-record ${DOMAIN} esx01m A 192.168.101.201
pdnsutil add-record ${DOMAIN} esx02m A 192.168.101.202q
pdnsutil add-record ${DOMAIN} esx03m A 192.168.101.203
pdnsutil add-record ${DOMAIN} esx04m A 192.168.101.204
pdnsutil add-record ${DOMAIN} switch01 A 192.168.252.1
pdnsutil add-record ${DOMAIN} switch02 A 192.168.252.2
pdnsutil add-record ${DOMAIN} switch03 A 192.168.252.3

for DOMAIN in `pdnsutil list-all-zones`; do 
 echo $z
 pdnsutil set-kind ${DOMAIN} primary
 pdnsutil set-meta ${DOMAIN} ALLOW-AXFR-FROM AUTO-NS 10.0.0.3
 pdnsutil set-meta ${DOMAIN} ALSO-NOTIFY 10.0.0.3
 pdnsutil set-meta ${DOMAIN} default-soa-name ns1.nf.lab
 pdnsutil set-meta ${DOMAIN} SOA-EDIT-DNSUPDATE DEFAULT 
 pdnsutil set-meta ${DOMAIN} SOA-EDIT-API DEFAULT  
 pdnsutil set-meta ${DOMAIN} SOA-EDIT INCEPTION-INCREMENT
 pdnsutil set-meta ${DOMAIN} TSIG-ALLOW-DNSUPDATE rndc-key
 pdnsutil set-meta ${DOMAIN} ALLOW-DNSUPDATE-FROM 0.0.0.0/0 ::/0 2603:6013::/32
 pdnsutil activate-tsig-key ${DOMAIN} rndc-key primary
done

for DOMAIN in `pdnsutil list-all-zones`
do 
 echo $z
  pdnsutil increase-serial ${DOMAIN}
done


for z in `cat /tmp/domains`; do  
  pdnsutil activate-tsig-key ${z} rndc-key primary
done
for ip in {50..250}; do
 pdnsutil add-record 0.2.10.in-addr.arpa ${ip} PTR dhcp_${ip}.okd.nf.lab.
 pdnsutil add-record okd.nf.lab dhcp_${ip} A 10.2.0.${ip}
done
pdnsutil add-record 0.3.10.in-addr.arpa 1 PTR fw.v1003.nf.lan
pdnsutil add-record 0.4.10.in-addr.arpa 1 PTR fw.v1004.nf.lan
pdnsutil add-record 0.5.10.in-addr.arpa 1 PTR fw.v1005.nf.lan
pdnsutil add-record 0.6.10.in-addr.arpa 1 PTR fw.v1006.nf.lan
pdnsutil add-record 0.7.10.in-addr.arpa 1 PTR fw.v1007.nf.lan
pdnsutil add-record 99.0.10.in-addr.arpa 1 PTR fw.v999.nf.lan
pdnsutil add-record 101.168.192.in-addr.arpa 1 PTR fw.v101.nf.lan


pdnsutil add-record v1000.nf.lan db A 10.0.0.20
pdnsutil add-record v1000.nf.lan dovecot A 10.0.0.30
pdnsutil add-record v1000.nf.lan emby A 10.0.0.31
pdnsutil add-record v1000.nf.lan influxdb A 10.0.0.22
pdnsutil add-record v1000.nf.lan kms A 10.0.0.26
pdnsutil add-record v1000.nf.lan mqtt A 10.0.0.27
pdnsutil add-record v1000.nf.lan postfix A 10.0.0.32
pdnsutil add-record v1000.nf.lan redis A 10.0.0.23

10.0.0. 192.168.101 192.168.252 192.168.253 192.168.254.1

for l in `grep "\.int\." /tmp/int|grep '192.168.254'|sed 's/.int.nforcer.com.//'|awk '{print $1":"$5}'`;do 
 h=`echo $l|cut -f1 -d:`
 ip=`echo $l|cut -f2 -d:`
 echo "pdnsutil add-record int.nforcer.com ${h} A ${ip}"
 echo "pdnsutil add-record 254.168.192.in-addr.arpa ${ip} PTR $h.int.nforcer.com."
done



cat > /etc/pdns/pdns.conf <<EOF
#Master
allow-axfr-ips=10.0.0.8/0,192.168.0.0/16
allow-dnsupdate-from=10.0.0.0/8,192.168.0.0/16

daemon=yes
setgid=pdns
setuid=pdns
guardian=no

cache-ttl=20
default-ttl=60
forward-dnsupdate=yes

launch=gsqlite3
gsqlite3-database=/opt/pdns/mydns

local-address=10.0.0.2
local-port=53

log-dns-details=yes
loglevel=3
query-logging=yes

dnsupdate=yes
master=yes

webserver-address=0.0.0.0
webserver-allow-from=0.0.0.0/0
webserver-port=8081
webserver=yes
api=true
api-key=4845460c-5012-46fe-8ece-56d95a8c3713
EOF

cat > /etc/pdns/recursor.conf <<EOF
# Recursor
allow-from=0.0.0.0/0

daemon=yes

forward-zones=int.nforcer.com=10.0.0.2;10.0.0.3
forward-zones+=ocp.nforcer.com=10.0.0.2;10.0.0.3
forward-zones+=okd.nforcer.com=10.0.0.2;10.0.0.3
forward-zones+=v1000.nforcer.com=10.0.0.2;10.0.0.3
forward-zones+=v1001.nforcer.com=10.0.0.2;10.0.0.3
forward-zones+=v1002.nforcer.com=10.0.0.2;10.0.0.3
forward-zones+=v1003.nforcer.com=10.0.0.2;10.0.0.3
forward-zones+=v999.nforcer.com=10.0.0.2;10.0.0.3
forward-zones+=v101.nforcer.com=10.0.0.2;10.0.0.3
forward-zones+=nf.lab=10.0.0.2;10.0.0.3
forward-zones+=v101.nf.lab=10.0.0.2;10.0.0.3
forward-zones+=v999.nf.lab=10.0.0.2;10.0.0.3
forward-zones+=v1000.nf.lab=10.0.0.2;10.0.0.3
forward-zones+=v1001.nf.lab=10.0.0.2;10.0.0.3
forward-zones+=v1002.nf.lab=10.0.0.2;10.0.0.3
forward-zones+=v1003.nf.lab=10.0.0.2;10.0.0.3
forward-zones+=ocp.nf.lab=10.0.0.2;10.0.0.3
forward-zones+=okd.nf.lab=10.0.0.2;10.0.0.3
forward-zones+=0.0.10.in-addr.arpa=10.0.0.2;10.0.0.3
forward-zones+=0.1.10.in-addr.arpa=10.0.0.2;10.0.0.3
forward-zones+=0.2.10.in-addr.arpa=10.0.0.2;10.0.0.3
forward-zones+=0.3.10.in-addr.arpa=10.0.0.2;10.0.0.3
forward-zones+=99.0.10.in-addr.arpa=10.0.0.2;10.0.0.3
forward-zones+=101.168.192.in-addr.arpa=10.0.0.2;10.0.0.3
forward-zones+=252.168.192.in-addr.arpa=10.0.0.2;10.0.0.3
forward-zones+=253.168.192.in-addr.arpa=10.0.0.2;10.0.0.3
forward-zones+=254.168.192.in-addr.arpa=10.0.0.2;10.0.0.3

hint-file=/etc/pdns/root.hints

local-address=10.0.0.4
local-port=53

setgid=recursor
setuid=recursor
EOF

cat > /etc/pdns/pdns.conf <<'EOF'
# Slave
allow-axfr-ips=10.0.0.0/8,192.168.0.0/16
allow-dnsupdate-from=10.0.0.0/8,192.168.0.0/16
allow-notify-from=10.0.0.0/8,192.168.0.0/16
allow-unsigned-notify=yes
allow-unsigned-supermaster=yes

daemon=yes
guardian=no
setgid=pdns
setuid=pdns

cache-ttl=20
expand-alias=no
webserver=no
resolver=no

launch=gsqlite3
gsqlite3-database=/opt/pdns/mydns

local-address=10.0.0.3
local-port=53

dnsupdate=yes
master=no
slave=yes
superslave=yes
EOF

cat <<EOF >/tmp/arpa
d.9.1.6.0.0.0.0.0.0.0.0.0.0.0.0.9.5.b.a.1.4.e.7.3.1.0.6.3.0.6.2.ip6.arpa
d.9.1.6.0.0.0.0.0.0.0.0.0.0.0.0.5.5.b.a.1.4.e.7.3.1.0.6.3.0.6.2.ip6.arpa
EOF


for DOMAIN in `cat /tmp/arpa`; do  
 echo $DOMAIN
 pdnsutil create-zone ${DOMAIN} ns1.nf.lab.
 pdnsutil add-record ${DOMAIN} @ NS ns2.nf.lab.
 pdnsutil set-kind ${DOMAIN} primary
 pdnsutil set-meta ${DOMAIN} default-soa-name ns1.nf.lab
 pdnsutil set-meta ${DOMAIN} SOA-EDIT-DNSUPDATE DEFAULT 
 pdnsutil set-meta ${DOMAIN} SOA-EDIT-API DEFAULT  
 pdnsutil set-meta ${DOMAIN} SOA-EDIT INCEPTION-INCREMENT
 pdnsutil set-meta ${DOMAIN} TSIG-ALLOW-DNSUPDATE rndc-key
 pdnsutil set-meta ${DOMAIN} ALLOW-DNSUPDATE-FROM 0.0.0.0/0 ::/0 2603::/16 2603:6013:7e41:ab50:a236:9fff:fece:e1fc
 pdnsutil activate-tsig-key ${DOMAIN} rndc-key master
done

for DOMAIN in `pdnsutil list-all-zones`
do 
 echo $z
  pdnsutil increase-serial ${DOMAIN}
done


for DOMAIN in `pdnsutil list-all-zones`; do 
  echo "Notify for $z"
  pdnsutil increase-serial ${DOMAIN}
  sleep 1 
  pdns_control notify ${DOMAIN}
done


DOMAIN=5.b.a.1.4.e.7.3.1.0.6.3.0.6.2.ip6.arpa
pdnsutil create-zone ${DOMAIN} ns1.nf.lab.
pdnsutil set-kind ${DOMAIN} primary
pdnsutil add-record ${DOMAIN} @ NS ns2.nf.lab.
pdnsutil set-kind ${DOMAIN} primary
pdnsutil set-meta ${DOMAIN} default-soa-name ns1.nf.lab
pdnsutil set-meta ${DOMAIN} SOA-EDIT-DNSUPDATE DEFAULT 
pdnsutil set-meta ${DOMAIN} SOA-EDIT-API DEFAULT  
pdnsutil set-meta ${DOMAIN} SOA-EDIT INCEPTION-INCREMENT
pdnsutil set-meta ${DOMAIN} ALLOW-DNSUPDATE-FROM 0.0.0.0/0 ::/0 2603::/16 2603:6013:7e41:ab50:a236:9fff:fece:e1fc
pdnsutil set-meta ${DOMAIN} TSIG-ALLOW-DNSUPDATE rndc-key
pdnsutil activate-tsig-key ${DOMAIN} rndc-key master


for DOMAIN in `pdnsutil list-all-zones`; do 
 echo $z
 pdnsutil set-meta ${DOMAIN} ALLOW-DNSUPDATE-FROM 0.0.0.0/0 ::/0 2603::/16 2603:6013:7e41:ab50:a236:9fff:fece:e1fc
done