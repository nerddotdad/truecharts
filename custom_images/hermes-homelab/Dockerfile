# Hermes WebUI + homelab kubectl/flux + bundled skills/extensions/scripts.
FROM ghcr.io/nesquena/hermes-webui:latest@sha256:0e793c6358dd4e5292ff62f5540ec67252c20b71c69d9933b4b73bbf7e80a610

USER root

RUN apt-get update \
    && apt-get install -y --no-install-recommends curl ca-certificates \
    && KVER="$(curl -fsSL https://dl.k8s.io/release/stable.txt)" \
    && curl -fsSL "https://dl.k8s.io/release/${KVER}/bin/linux/amd64/kubectl" -o /usr/local/bin/kubectl \
    && chmod +x /usr/local/bin/kubectl \
    && curl -fsSL https://github.com/fluxcd/flux2/releases/download/v2.7.2/flux_2.7.2_linux_amd64.tar.gz \
       | tar -xz -C /usr/local/bin flux \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

COPY skills /opt/homelab-skills/
COPY scripts /opt/homelab-scripts/
COPY extensions /opt/hermes-extensions/

# Seed Ollama provider when config.yaml does not exist yet (PVC first boot).
COPY config.yaml /opt/hermes-seed/config.yaml

# Upstream CMD is /hermeswebui_init.bash — must run as root (UID setup + volume prep).
RUN printf '%s\n' \
  '#!/bin/sh' \
  'set -e' \
  'if [ -f /opt/hermes-seed/config.yaml ] && [ ! -f /home/hermeswebui/.hermes/config.yaml ]; then' \
  '  mkdir -p /home/hermeswebui/.hermes' \
  '  cp /opt/hermes-seed/config.yaml /home/hermeswebui/.hermes/config.yaml' \
  'fi' \
  'exec /hermeswebui_init.bash "$@"' \
  > /hermes-homelab-entry.sh \
  && chmod 755 /hermes-homelab-entry.sh

USER root
CMD ["/hermes-homelab-entry.sh"]
