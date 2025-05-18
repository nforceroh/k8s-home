#!/bin/bash

mkdir -p data_sources && curl -s "https://grafana.k3s.nf.lab/api/datasources"  -u admin:admin|jq -c -M '.[]'|split -l 1 - data_sources/
