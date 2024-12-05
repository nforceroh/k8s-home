# add internal cert for idrac
```
step ca bootstrap --ca-url https://ca.nf.lab --fingerprint 50469643a11b4e72f2dd2eddae5c90d8b90acf1c51b2ab8ccba9391b5b97d9bc
step ca certificate --san virt01m.v101.nf.lab --san 192.168.101.200 virt01m.v101.nf.lab certs/virt01m.v101.nf.lab.crt certs/virt01m.v101.nf.lab.key --not-after=87000h -set emailAddresses=sylvain@nf.lab --kty RSA
```

# Install racadm
https://www.privex.io/articles/install-idrac-tools-racadm-ubuntu-debian/


# install cert
export PW=
export IP=192.168.101.200
racadm -r ${IP} -u root -p ${PW} sslkeyupload -t 1 -f certs/virt01m.v101.nf.lab.key
racadm -r ${IP} -u root -p ${PW} sslcertupload -t 1 -f certs/virt01m.v101.nf.lab.crt
racadm -r ${IP} -u root -p ${PW} racreset 
```