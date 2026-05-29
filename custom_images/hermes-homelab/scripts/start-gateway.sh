#!/bin/sh
# Background Hermes gateway + webhook subscriptions for ntfy Ask AI triage.
set -e

HERMES_HOME="${HERMES_HOME:-/home/hermeswebui/.hermes}"
WEBHOOK_PORT="${WEBHOOK_PORT:-8644}"
WEBHOOK_SECRET="${WEBHOOK_SECRET:-${HERMES_WEBHOOK_SECRET:-}}"

if [ "${WEBHOOK_ENABLED:-false}" != "true" ]; then
  exit 0
fi

if [ -z "$WEBHOOK_SECRET" ]; then
  echo "start-gateway: WEBHOOK_SECRET not set; skipping gateway" >&2
  exit 0
fi

export HERMES_HOME
export WEBHOOK_ENABLED=true
export WEBHOOK_PORT
export WEBHOOK_SECRET

wait_for_hermes() {
  i=0
  while [ "$i" -lt 120 ]; do
    if command -v hermes >/dev/null 2>&1; then
      return 0
    fi
    if [ -f "$HERMES_HOME/hermes-agent/run_agent.py" ]; then
      export PATH="${HERMES_HOME}/venv/bin:${PATH}"
      if command -v hermes >/dev/null 2>&1; then
        return 0
      fi
    fi
    i=$((i + 1))
    sleep 5
  done
  echo "start-gateway: hermes CLI not available after waiting" >&2
  return 1
}

ensure_webhook_subscription() {
  if hermes webhook list 2>/dev/null | grep -q 'homelab-alerts'; then
    return 0
  fi
  hermes webhook subscribe homelab-alerts \
    --prompt "Homelab alert triage from ntfy Ask AI. Use read-only kubectl and flux.

1. If the payload includes alert.annotations.runbook_url, treat that as the primary runbook.
2. Otherwise map alert.labels.alertname to homelab runbooks under \$HOMELAB_DOCS_BASE_URL (see skill homelab-k8s-flux-triage).
3. Cite doc links in your reply; do not guess URLs.

Incident JSON:

{__raw__}" \
    --skills homelab-k8s-flux-triage \
    --secret "$WEBHOOK_SECRET"
}

wait_for_hermes || exit 0
ensure_webhook_subscription || true
exec hermes gateway run
