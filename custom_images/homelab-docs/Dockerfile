# Build static docs from co-located clusters/**/mk_*.md (repo root context).
FROM python:3.12-slim AS builder

WORKDIR /src

COPY mkdocs/requirements.txt mkdocs/requirements.txt
RUN pip install --no-cache-dir -r mkdocs/requirements.txt

COPY scripts/collect_mkdocs.py scripts/collect_mkdocs.py
COPY scripts/helmrelease_docs.py scripts/helmrelease_docs.py
COPY scripts/runbook_index.py scripts/runbook_index.py
COPY mkdocs/mkdocs.base.yml mkdocs/mkdocs.base.yml
COPY mkdocs/templates mkdocs/templates
COPY mkdocs/snippets mkdocs/snippets
COPY clusters clusters

# Required for navigation.instant (non-empty sitemap). Override at build time to match ingress host.
ARG MKDOCS_SITE_URL=https://docs.example.com
ENV MKDOCS_SITE_URL=${MKDOCS_SITE_URL}

RUN python scripts/collect_mkdocs.py \
    && mkdocs build -f mkdocs/mkdocs.generated.yml

FROM nginxinc/nginx-unprivileged:stable-alpine

COPY --from=builder /src/mkdocs/site /usr/share/nginx/html

EXPOSE 8080
