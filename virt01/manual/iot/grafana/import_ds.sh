#!/bin/bash

for i in data_sources/*; do \
    curl -k -X "POST" "https://grafana.apps.ocp.nf.lab/api/datasources" \
    -H "Content-Type: application/json" \
     --user admin:G0tR0gu3\! \
     --data-binary @$i
done