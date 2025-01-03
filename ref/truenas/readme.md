# rsync
```
rsync -aHAXxv --numeric-ids --delete --progress -e "ssh -T -o Compression=no -x" /mnt/spins/depot root@virt01.v1001.nf.lab:/mnt/ssd01 
rsync -aHAXxv --numeric-ids --delete --progress -e "ssh -T -o Compression=no -x" /mnt/spins/backup root@virt01.v1001.nf.lab:/mnt/ssd01 
rsync -aHAXxv --numeric-ids --delete --progress -e "ssh -T -o Compression=no -x" /mnt/spins/emby root@virt01.v1001.nf.lab:/mnt/ssd01 
rsync -aHAXxv --numeric-ids --delete --progress -e "ssh -T -c arcfour -o Compression=no -x" /mnt/spins/Music root@virt01.v1001.nf.lab:/mnt/ssd01 
```

for s in backup depot emby Music; do rsync -aHAXxv --numeric-ids --delete --progress -e "ssh -T -o Compression=no -x" /mnt/ssd01/$s/* nas02.v101.nf.lab:/mnt/spins/$s ; done
for s in backup depot Music; do rsync -aHAXxv --numeric-ids --delete --progress -e "ssh -T -o Compression=no -x" /mnt/spins/$s/* root@virt01.v1001.nf.lab:/mnt/ssd01/$s ; done

# Create a cert for the webui
```
step ca bootstrap --ca-url https://ca.nf.lab --fingerprint 50469643a11b4e72f2dd2eddae5c90d8b90acf1c51b2ab8ccba9391b5b97d9bc
mkdir certs
step ca certificate --san nas01.v1000.nf.lab --san nas01.nf.lab --san 10.0.0.100 nas01.v1000.nf.lab certs/nas01.v1000.nf.lab.crt certs/nas01.v1000.nf.lab.key --not-after=87000h
```

# add root certs
```
cd ~/
cat > nf_lab_intermediate_ca.crt <<EOF
-----BEGIN CERTIFICATE-----
MIIBvzCCAWagAwIBAgIQU9EaPXfERZ4zHExBjiiCdTAKBggqhkjOPQQDAjAqMQ8w
DQYDVQQKEwZuZi5sYWIxFzAVBgNVBAMTDm5mLmxhYiBSb290IENBMB4XDTIzMDkw
NzAyMDYzNFoXDTMzMDkwNDAyMDYzNFowMjEPMA0GA1UEChMGbmYubGFiMR8wHQYD
VQQDExZuZi5sYWIgSW50ZXJtZWRpYXRlIENBMFkwEwYHKoZIzj0CAQYIKoZIzj0D
AQcDQgAEJ9IDnHYSBP0Zqu52WAwKWOqUaE3aMYKYCEZymZ1uxQ9aJQa/07uzTnW6
Vyt+T9p4oR36emzLb8UAK5wlvKC7xqNmMGQwDgYDVR0PAQH/BAQDAgEGMBIGA1Ud
EwEB/wQIMAYBAf8CAQAwHQYDVR0OBBYEFHsSx3fFbKz81GtwFHh/n598bpZ7MB8G
A1UdIwQYMBaAFPN50HuutUiXeksGg3uGLjCF605hMAoGCCqGSM49BAMCA0cAMEQC
IEZCwEcgHaFQdwmNElARcSj1VpqVR/6kZHosbqHnKkiaAiA7pw+1ehtOw/jmOGKS
iHfp87h4ssrokpRDE1fnEdobtA==
-----END CERTIFICATE-----
EOF

cat >nf_lab_root_ca.crt <<EOF
-----BEGIN CERTIFICATE-----
MIIBmTCCAT6gAwIBAgIRAMZA2d93OfSMpAURmdtuFUwwCgYIKoZIzj0EAwIwKjEP
MA0GA1UEChMGbmYubGFiMRcwFQYDVQQDEw5uZi5sYWIgUm9vdCBDQTAeFw0yMzA5
MDcwMjA2MzNaFw0zMzA5MDQwMjA2MzNaMCoxDzANBgNVBAoTBm5mLmxhYjEXMBUG
A1UEAxMObmYubGFiIFJvb3QgQ0EwWTATBgcqhkjOPQIBBggqhkjOPQMBBwNCAAQG
ltaagHEyYDkdreE+B0fQF4QgDRQOD3FGYxCdsH4X8HL6qtNgm+o1j2Eu6fI8Zku8
EuAS5LrsuP2nzLj8gweHo0UwQzAOBgNVHQ8BAf8EBAMCAQYwEgYDVR0TAQH/BAgw
BgEB/wIBATAdBgNVHQ4EFgQU83nQe661SJd6SwaDe4YuMIXrTmEwCgYIKoZIzj0E
AwIDSQAwRgIhAInXZD7+T22lKxtZa0I5QhP4BGwMDQM/S6r/yAiQTyNmAiEAmT1d
nYAUziEmQnmNzcD7s/M3gSv1T1a1d3LtYrNn2Eg=
-----END CERTIFICATE-----
EOF

cp nf_lab_intermediate_ca.crt /usr/local/share/ca-certificates
cp nf_lab_root_ca.crt /usr/local/share/ca-certificates

update-ca-certificates --verbose
```
