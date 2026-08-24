#!/bin/sh
# relayer-forward.sh -- forwards the raw message to Relayer's /ingest endpoint.
#
# Runs as a Dovecot Sieve `pipe :copy` target for every mailbox on the
# server. Deliberately dumb: no MySQL knowledge, no mailbox-specific logic
# here at all -- Relayer decides what (if anything) happens.
#
# Lands in /data/sieve via the existing sieve-init script (copy from
# /configfiles/sieve, chmod +x for *.sh, chown vmail:mail) -- no special
# handling needed here beyond that.
#
# Always exits 0. A forwarding hiccup must never block or delay real
# mailbox delivery.

TOKEN_PATH="/etc/dovecot/secrets/relayer-token"
RELAYER_URL="http://relayer-svc.mail.svc.cluster.local:8080/ingest"
TIMEOUT_SECONDS=5

TOKEN=$(cat "$TOKEN_PATH" 2>/dev/null)

if [ -z "$TOKEN" ]; then
  # Never block delivery over this, but at least leave a trail: stderr
  # from Sieve pipe scripts is written to the LDA/sieve log, so this is
  # visible in Dovecot's own logs without needing to cross-check Relayer.
  echo "relayer-forward: WARNING: token empty or unreadable at $TOKEN_PATH (running as $(id -un 2>/dev/null))" >&2
fi

curl -s -m "$TIMEOUT_SECONDS" -X POST \
  -H "Authorization: Bearer ${TOKEN}" \
  --data-binary @- \
  "$RELAYER_URL" >/dev/null 2>&1

exit 0