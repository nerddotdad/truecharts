#!/bin/sh
# Hermes gateway daemon for webhooks (ntfy Ask AI) and WebUI health (cron ticks).
# Must run as hermeswebui — WebUI reads ~/.hermes/gateway_state.json (see hermes-webui #1879).
# https://github.com/nesquena/hermes-webui/blob/master/docs/docker.md#scheduled-jobs-and-the-gateway-daemon
set -eu

HERMES_HOME="${HERMES_HOME:-/home/hermeswebui/.hermes}"
WEBHOOK_PORT="${WEBHOOK_PORT:-8644}"
WEBHOOK_SECRET="${WEBHOOK_SECRET:-${HERMES_WEBHOOK_SECRET:-}}"
HERMES_BIN="${HERMES_BIN:-/app/venv/bin/hermes}"
HERMES_USER="${HERMES_USER:-hermeswebui}"

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
export HERMES_BIN

run_as_hermes_user() {
  # Background starter runs as root; gateway + state files must be owned by the WebUI user.
  if [ "$(id -u)" -eq 0 ] && id "$HERMES_USER" >/dev/null 2>&1; then
    su -s /bin/sh "$HERMES_USER" -c "$1"
  else
    sh -c "$1"
  fi
}

resolve_hermes_bin() {
  if [ -x "$HERMES_BIN" ]; then
    return 0
  fi
  if [ -x "${HERMES_HOME}/venv/bin/hermes" ]; then
    HERMES_BIN="${HERMES_HOME}/venv/bin/hermes"
    export HERMES_BIN
    return 0
  fi
  if command -v hermes >/dev/null 2>&1; then
    HERMES_BIN="$(command -v hermes)"
    export HERMES_BIN
    return 0
  fi
  return 1
}

wait_for_hermes_bin() {
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
  run_as_hermes_user "
    export HERMES_HOME='$HERMES_HOME' WEBHOOK_SECRET='$WEBHOOK_SECRET' WEBHOOK_PORT='$WEBHOOK_PORT'
    /app/venv/bin/python /opt/homelab-scripts/ensure-homelab-config.py
  "
}

ensure_webhook_subscription() {
  run_as_hermes_user "
    export HERMES_HOME='$HERMES_HOME' WEBHOOK_SECRET='$WEBHOOK_SECRET' WEBHOOK_PORT='$WEBHOOK_PORT' HERMES_BIN='$HERMES_BIN'
    SUB_FILE=\"\$HERMES_HOME/webhook_subscriptions.json\"
    if \"\$HERMES_BIN\" webhook list 2>/dev/null | grep -q 'homelab-alerts'; then
      if [ -f \"\$SUB_FILE\" ] && grep -q 'Homelab alert triage from ntfy' \"\$SUB_FILE\" 2>/dev/null; then
        exit 0
      fi
      \"\$HERMES_BIN\" webhook unsubscribe homelab-alerts 2>/dev/null || true
    fi
    \"\$HERMES_BIN\" webhook subscribe homelab-alerts \
      --prompt 'Homelab alert triage from ntfy Ask AI. Use read-only kubectl and flux.

1. If the payload includes alert.annotations.runbook_url, treat that as the primary runbook.
2. Otherwise map alert.labels.alertname to homelab runbooks under HOMELAB_DOCS_BASE_URL (see skill homelab-k8s-flux-triage).
3. For jellyfin_* alerts or media playback issues, use skill jellyfin-api (JELLYFIN_API_URL + JELLYFIN_API_TOKEN) alongside homelab-k8s-flux-triage.
4. Cite doc links in your reply; do not guess URLs.

Incident JSON:

{__raw__}' \
      --skills homelab-k8s-flux-triage,jellyfin-api \
      --secret \"\$WEBHOOK_SECRET\"
  "
}

fix_stale_gateway_artifacts() {
  # Root-owned gateway files from older images block WebUI health checks.
  if [ "$(id -u)" -eq 0 ]; then
    for f in "$HERMES_HOME/gateway.pid" "$HERMES_HOME/gateway.lock" "$HERMES_HOME/gateway_state.json"; do
      if [ -e "$f" ]; then
        chown "$HERMES_USER:$HERMES_USER" "$f" 2>/dev/null || true
        chmod 640 "$f" 2>/dev/null || true
      fi
    done
  fi
}

run_gateway_loop() {
  while true; do
    if ! wait_for_hermes_bin; then
      sleep 30
      continue
    fi
    fix_stale_gateway_artifacts
    if ! ensure_webhook_platform; then
      echo "start-gateway: failed to merge webhook platform into config.yaml" >&2
      sleep 30
      continue
    fi
    ensure_webhook_subscription || true
    echo "start-gateway: running gateway on :${WEBHOOK_PORT} as ${HERMES_USER} ($(date -u +%Y-%m-%dT%H:%M:%SZ))" >&2
    run_as_hermes_user "
      export HERMES_HOME='$HERMES_HOME' WEBHOOK_ENABLED=true WEBHOOK_PORT='$WEBHOOK_PORT' WEBHOOK_SECRET='$WEBHOOK_SECRET' HERMES_BIN='$HERMES_BIN'
      exec \"\$HERMES_BIN\" gateway run
    " || true
    echo "start-gateway: gateway exited; retrying in 15s" >&2
    sleep 15
  done
}

run_gateway_loop
