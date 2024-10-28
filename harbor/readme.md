```
wget https://dl.smallstep.com/cli/docs-ca-install/latest/step-cli_amd64.deb
sudo dpkg -i step-cli_amd64.deb

wget https://dl.smallstep.com/certificates/docs-ca-install/latest/step-ca_amd64.deb
sudo dpkg -i step-ca_amd64.deb


step ca bootstrap --ca-url https://ca.nf.lab:8443 --fingerprint 50469643a11b4e72f2dd2eddae5c90d8b90acf1c51b2ab8ccba9391b5b97d9bc

step ca certificate --san harbor.nf.lab harbor.nf.lab harbor.nf.lab.crt harbor.nf.lab.key --not-after=87000h
 
wget https://github.com/goharbor/harbor/releases/download/v2.11.1/harbor-online-installer-v2.11.1.tgz

tar xvf harbor-online-installer-v2.11.1.tgz

```