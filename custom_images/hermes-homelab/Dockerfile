# Hermes WebUI + homelab kubectl/flux + bundled skills/extensions/scripts.
FROM ghcr.io/nesquena/hermes-webui:latest@sha256:20feeb031e7565d404237e1020e427e917d41115de54d329adbe443c1c08bf08

USER root

# Hermes Agent source — docker_init.bash installs from /opt/hermes or ~/.hermes/hermes-agent.
ARG HERMES_AGENT_REF=main
RUN apt-get update \
    && apt-get install -y --no-install-recommends curl ca-certificates git \
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

# Skills/SOUL/USER: GitOps ConfigMaps in hermes-oncall/app/agent-config/ (not baked in image).
COPY scripts /opt/homelab-scripts/
COPY extensions /opt/hermes-extensions/

# Seed Ollama provider when config.yaml does not exist yet (PVC first boot).
COPY config.yaml /opt/hermes-seed/config.yaml

# Upstream CMD is /hermeswebui_init.bash — must run as root (UID setup + volume prep).
RUN chmod 755 /opt/homelab-scripts/start-gateway.sh \
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
  'exec /hermeswebui_init.bash "$@"' \
  > /hermes-homelab-entry.sh \
  && chmod 755 /hermes-homelab-entry.sh

ENV HERMES_BUNDLED_PLUGINS=/opt/hermes/plugins

USER root
CMD ["/hermes-homelab-entry.sh"]
