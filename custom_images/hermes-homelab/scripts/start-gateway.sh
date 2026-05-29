#!/bin/sh
# Hermes gateway daemon for webhooks (ntfy Ask AI → homelab-alert-bridge → /webhooks/homelab-alerts).
# Single-container WebUI does not start the gateway; see:
# https://github.com/nesquena/hermes-webui/blob/master/docs/docker.md#scheduled-jobs-and-the-gateway-daemon
set -eu

HERMES_HOME="${HERMES_HOME:-/home/hermeswebui/.hermes}"
WEBHOOK_PORT="${WEBHOOK_PORT:-8644}"
WEBHOOK_SECRET="${WEBHOOK_SECRET:-${HERMES_WEBHOOK_SECRET:-}}"
HERMES_BIN="${HERMES_BIN:-/app/venv/bin/hermes}"

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

resolve_hermes_bin() {
  if [ -x "$HERMES_BIN" ]; then
    return 0
  fi
  if [ -x "${HERMES_HOME}/venv/bin/hermes" ]; then
    HERMES_BIN="${HERMES_HOME}/venv/bin/hermes"
    return 0
  fi
  if command -v hermes >/dev/null 2>&1; then
    HERMES_BIN="$(command -v hermes)"
    return 0
  fi
  return 1
}

wait_for_hermes_bin() {
  # WebUI installs hermes-agent into /app/venv during docker_init (several minutes on first boot).
  i=0
  while [ "$i" -lt 360 ]; do
    if resolve_hermes_bin; then
      return 0
    fi
    i=$((i + 1))
    sleep 5
  done
  echo "start-gateway: hermes CLI not found (expected ${HERMES_BIN})" >&2
  return 1
}

ensure_webhook_platform() {
  /app/venv/bin/python /opt/homelab-scripts/ensure-webhook-platform.py
}

ensure_webhook_subscription() {
  if "$HERMES_BIN" webhook list 2>/dev/null | grep -q 'homelab-alerts'; then
    return 0
  fi
  "$HERMES_BIN" webhook subscribe homelab-alerts \
    --prompt "Homelab alert triage from ntfy Ask AI. Use read-only kubectl and flux.

1. If the payload includes alert.annotations.runbook_url, treat that as the primary runbook.
2. Otherwise map alert.labels.alertname to homelab runbooks under HOMELAB_DOCS_BASE_URL (see skill homelab-k8s-flux-triage).
3. Cite doc links in your reply; do not guess URLs.

Incident JSON:

{__raw__}" \
    --skills homelab-k8s-flux-triage \
    --secret "$WEBHOOK_SECRET"
}

run_gateway_loop() {
  while true; do
    if ! wait_for_hermes_bin; then
      sleep 30
      continue
    fi
    if ! ensure_webhook_platform; then
      echo "start-gateway: failed to merge webhook platform into config.yaml" >&2
      sleep 30
      continue
    fi
    ensure_webhook_subscription || true
    echo "start-gateway: running gateway on :${WEBHOOK_PORT} ($(date -u +%Y-%m-%dT%H:%M:%SZ))" >&2
    "$HERMES_BIN" gateway run || true
    echo "start-gateway: gateway exited; retrying in 15s" >&2
    sleep 15
  done
}

run_gateway_loop
