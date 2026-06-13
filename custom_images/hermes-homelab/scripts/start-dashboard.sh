#!/bin/sh
# Hermes Agent management dashboard (hermes dashboard) — config, logs, skills, gateway status.
# https://hermes-agent.nousresearch.com/docs/user-guide/features/web-dashboard
set -eu

HERMES_HOME="${HERMES_HOME:-/home/hermeswebui/.hermes}"
DASHBOARD_PORT="${DASHBOARD_PORT:-9119}"
GATEWAY_HEALTH_URL="${GATEWAY_HEALTH_URL:-http://127.0.0.1:8644}"
HERMES_BIN="${HERMES_BIN:-/app/venv/bin/hermes}"
HERMES_USER="${HERMES_USER:-hermeswebui}"

if [ "${DASHBOARD_ENABLED:-true}" != "true" ]; then
  exit 0
fi

export HERMES_HOME
export DASHBOARD_PORT
export GATEWAY_HEALTH_URL
export HERMES_BIN

# Resolve packaged web_dist (pip install) or image-baked /opt/hermes copy.
if [ -z "${HERMES_WEB_DIST:-}" ]; then
  _web_index="$(find /app/venv/lib -path '*/hermes_cli/web_dist/index.html' 2>/dev/null | head -1 || true)"
  if [ -n "$_web_index" ]; then
    HERMES_WEB_DIST="$(dirname "$_web_index")"
  elif [ -f /opt/hermes/hermes_cli/web_dist/index.html ]; then
    HERMES_WEB_DIST=/opt/hermes/hermes_cli/web_dist
  fi
fi
if [ -n "${HERMES_WEB_DIST:-}" ]; then
  export HERMES_WEB_DIST
fi

run_as_hermes_user() {
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
  echo "start-dashboard: hermes CLI not found (expected ${HERMES_BIN})" >&2
  return 1
}

run_dashboard_loop() {
  while true; do
    if ! wait_for_hermes_bin; then
      sleep 30
      continue
    fi
    echo "start-dashboard: running on 0.0.0.0:${DASHBOARD_PORT} as ${HERMES_USER} ($(date -u +%Y-%m-%dT%H:%M:%SZ))" >&2
    run_as_hermes_user "
      export HERMES_HOME='$HERMES_HOME' GATEWAY_HEALTH_URL='$GATEWAY_HEALTH_URL' HERMES_BIN='$HERMES_BIN'
      export HERMES_WEB_DIST='${HERMES_WEB_DIST:-}'
      export HERMES_DASHBOARD_PUBLIC_URL='${HERMES_DASHBOARD_PUBLIC_URL:-}'
      export HERMES_DASHBOARD_TUI='${HERMES_DASHBOARD_TUI:-1}'
      exec \"\$HERMES_BIN\" dashboard --host 0.0.0.0 --port '$DASHBOARD_PORT' --no-open --insecure --tui
    " || true
    echo "start-dashboard: dashboard exited; retrying in 15s" >&2
    sleep 15
  done
}

run_dashboard_loop
