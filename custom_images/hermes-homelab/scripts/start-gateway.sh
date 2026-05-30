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
    export HERMES_BUNDLED_SKILLS='${HERMES_BUNDLED_SKILLS:-/opt/hermes/skills}'
    export HERMES_BUNDLED_PLUGINS='${HERMES_BUNDLED_PLUGINS:-/opt/hermes/plugins}'
    export HOMELAB_GITOPS_AGENT_DIR='${HOMELAB_GITOPS_AGENT_DIR:-/opt/hermes-gitops}'
    export HERMES_GITOPS_PROFILES_DIR='${HERMES_GITOPS_PROFILES_DIR:-/opt/hermes-gitops-profiles}'
    /app/venv/bin/python /opt/homelab-scripts/ensure-homelab-config.py
  "
}

ensure_webhook_subscription() {
  run_as_hermes_user "
    export HERMES_HOME='$HERMES_HOME' WEBHOOK_SECRET='$WEBHOOK_SECRET' WEBHOOK_PORT='$WEBHOOK_PORT' HERMES_BIN='$HERMES_BIN'
    SUB_FILE=\"\$HERMES_HOME/webhook_subscriptions.json\"
    if \"\$HERMES_BIN\" webhook list 2>/dev/null | grep -q 'homelab-alerts'; then
      if [ -f \"\$SUB_FILE\" ] && grep -q 'homelab-webhook/v2' \"\$SUB_FILE\" 2>/dev/null; then
        exit 0
      fi
      \"\$HERMES_BIN\" webhook unsubscribe homelab-alerts 2>/dev/null || true
    fi
    \"\$HERMES_BIN\" webhook subscribe homelab-alerts \
      --prompt 'Homelab alert incident (follow SOUL.md and USER.md; use alert.annotations.recommended_ai_skills when set):

{__raw__}' \
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
