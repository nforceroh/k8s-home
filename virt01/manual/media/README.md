# Manual media applications

Sonarr and Radarr are manually deployed under `virt01/manual/`, outside Argo CD.
Their API-level blocking rules are therefore not part of the Kubernetes
manifests. Recreate the rules after a fresh app configuration with
[`scripts/configure_blocking_releases.py`](./scripts/configure_blocking_releases.py).

## Recreate Sonarr and Radarr blocking rules

The script uses the Sonarr and Radarr API URLs and tokens from environment
variables or a private `KEY=VALUE` env file. It also reads `SSL_CERT_FILE` when
provided; TLS certificate verification remains enabled.

Run a read-only preview first:

```bash
python3 virt01/manual/media/scripts/configure_blocking_releases.py \
  --env-file "$HOME/gitdev/k8s-home-secrets/mcp/arr-mcp.env"
```

Apply the configuration:

```bash
python3 virt01/manual/media/scripts/configure_blocking_releases.py \
  --env-file "$HOME/gitdev/k8s-home-secrets/mcp/arr-mcp.env" \
  --apply
```

The script can be limited to one application with `--app sonarr` or
`--app radarr`. It is safe to rerun: it finds the managed Custom Format and
Release Profiles by name, updates them in place when needed, and sets the
blocking score in every existing Quality Profile. Run it again after adding a
new Quality Profile.

The setup includes:

- A release-title Custom Format named **Block Malware and Banned Release Terms**.
- A score of **-9999** for that format in every Quality Profile; the minimum
  custom-format score remains unchanged.
- Global Release Profiles **Banned - release terms** and
  **Banned - non-media extensions**, with no indexer or tag restriction.

The rules inspect the release title only. They cannot detect an executable
hidden inside a torrent when the title does not disclose it. Broad release
terms such as CAM, TS, and TC can also reject legitimate titles.

Keep API tokens and CA files in the existing private secrets workflow; do not
add them to this repository.
