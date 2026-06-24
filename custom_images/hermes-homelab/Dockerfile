# Hermes WebUI + homelab kubectl/flux + bundled skills/scripts.
ARG HERMES_AGENT_REF=main

# `hermes dashboard` serves a Vite-built SPA from hermes_cli/web_dist (not shipped pre-built on PyPI).
FROM node:22-bookworm-slim@sha256:5d7730838f61b227480a7536103a3223d9f2f87c015ff0b11d9318647b2a7a3a AS dashboard-web
ARG HERMES_AGENT_REF
RUN apt-get update \
    && apt-get install -y --no-install-recommends git ca-certificates \
    && git clone --depth 1 --branch "${HERMES_AGENT_REF}" \
      https://github.com/NousResearch/hermes-agent.git /opt/hermes \
    && cd /opt/hermes/web && npm ci && npm run build \
    && test -f /opt/hermes/hermes_cli/web_dist/index.html \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

FROM ghcr.io/nesquena/hermes-webui:latest@sha256:eb8db88ca48ddcedc423c45b4283e563ca324a8af54a948c21998ac76ec41467

USER root

# Hermes Agent source — docker_init.bash installs from /opt/hermes or ~/.hermes/hermes-agent.
ARG HERMES_AGENT_REF
RUN apt-get update \
    && apt-get install -y --no-install-recommends \
      curl ca-certificates git jq \
      coreutils procps findutils grep sed gawk less \
      vim-tiny iproute2 iputils-ping dnsutils netcat-openbsd \
      util-linux tar gzip \
    && git clone --depth 1 --branch "${HERMES_AGENT_REF}" \
      https://github.com/NousResearch/hermes-agent.git /opt/hermes \
    && test -f /opt/hermes/run_agent.py \
    && test -f /opt/hermes/pyproject.toml \
    && KVER="$(curl -fsSL https://dl.k8s.io/release/stable.txt)" \
    && curl -fsSL "https://dl.k8s.io/release/${KVER}/bin/linux/amd64/kubectl" -o /usr/local/bin/kubectl \
    && chmod +x /usr/local/bin/kubectl \
    && curl -fsSL https://github.com/fluxcd/flux2/releases/download/v2.7.2/flux_2.7.2_linux_amd64.tar.gz \
       | tar -xz -C /usr/local/bin flux \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

COPY --from=dashboard-web /opt/hermes/hermes_cli/web_dist /opt/hermes/hermes_cli/web_dist

# Pre-bake WebUI + Hermes Agent into /apptoo/venv. docker_init.bash rsyncs /apptoo → /app on
# every start; .deps_installed skips the ~5–10 min runtime uv pip install.
ENV UV_CACHE_DIR=/uv_cache
RUN mkdir -p "${UV_CACHE_DIR}" \
  && cd /apptoo \
  && uv venv venv \
  && uv pip install --python venv/bin/python3 -r requirements.txt \
      --trusted-host pypi.org --trusted-host files.pythonhosted.org \
  && uv pip install --python venv/bin/python3 -U pip setuptools \
      --trusted-host pypi.org --trusted-host files.pythonhosted.org \
  && uv pip install --python venv/bin/python3 "/opt/hermes[all]" \
      --trusted-host pypi.org --trusted-host files.pythonhosted.org \
  && test -n "$(find venv/lib -path '*/hermes_cli/web_dist/index.html' -print -quit)" \
  && uv pip install --python venv/bin/python3 "hindsight-client>=0.4.22" \
      --trusted-host pypi.org --trusted-host files.pythonhosted.org \
  && touch venv/.deps_installed \
  && chown -R hermeswebui:hermeswebui venv "${UV_CACHE_DIR}"

# SOUL, skills, profiles, and model config live on the hermes-data PVC (not baked in image).
COPY scripts /opt/homelab-scripts/

# Seed Ollama provider when config.yaml does not exist yet (PVC first boot).
COPY config.yaml /opt/hermes-seed/config.yaml

# Upstream CMD is /hermeswebui_init.bash — must run as root (UID setup + volume prep).
RUN chmod 755 /opt/homelab-scripts/start-gateway.sh \
  /opt/homelab-scripts/start-dashboard.sh \
  /opt/homelab-scripts/ensure-webhook-platform.py \
  /opt/homelab-scripts/ensure-homelab-config.py \
  && printf '%s\n' \
  '#!/bin/sh' \
  'set -e' \
  'if [ -f /opt/hermes-seed/config.yaml ] && [ ! -f /home/hermeswebui/.hermes/config.yaml ]; then' \
  '  mkdir -p /home/hermeswebui/.hermes' \
  '  cp /opt/hermes-seed/config.yaml /home/hermeswebui/.hermes/config.yaml' \
  'fi' \
  'if [ ! -e /home/hermeswebui/.hermes/hermes-agent ] && [ -f /opt/hermes/run_agent.py ]; then' \
  '  ln -sfn /opt/hermes /home/hermeswebui/.hermes/hermes-agent' \
  'fi' \
  'if [ "${WEBHOOK_ENABLED:-false}" = "true" ]; then' \
  '  /opt/homelab-scripts/start-gateway.sh &' \
  'fi' \
  'if [ "${DASHBOARD_ENABLED:-true}" = "true" ]; then' \
  '  /opt/homelab-scripts/start-dashboard.sh &' \
  'fi' \
  'exec /hermeswebui_init.bash "$@"' \
  > /hermes-homelab-entry.sh \
  && chmod 755 /hermes-homelab-entry.sh

ENV HERMES_BUNDLED_SKILLS=/opt/hermes/skills \
    HERMES_BUNDLED_PLUGINS=/opt/hermes/plugins

USER root
CMD ["/hermes-homelab-entry.sh"]
