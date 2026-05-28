# Build static docs from co-located clusters/**/mk_*.md (repo root context).
FROM python:3.14-slim@sha256:c845af9399020c7e562969a13689e929074a10fd057acd1b1fad06a2fb068e97 AS builder

WORKDIR /src

# mkdocs-git-revision-date-localized + collect_mkdocs freshness need the git CLI (not just .git/).
RUN apt-get update \
    && apt-get install -y --no-install-recommends git \
    && rm -rf /var/lib/apt/lists/*

COPY mkdocs/requirements.txt mkdocs/requirements.txt
RUN pip install --no-cache-dir -r mkdocs/requirements.txt

COPY scripts/collect_mkdocs.py scripts/collect_mkdocs.py
COPY scripts/doc_metadata.py scripts/doc_metadata.py
COPY scripts/helmrelease_docs.py scripts/helmrelease_docs.py
COPY scripts/runbook_index.py scripts/runbook_index.py
COPY mkdocs/mkdocs.base.yml mkdocs/mkdocs.base.yml
COPY mkdocs/templates mkdocs/templates
COPY mkdocs/snippets mkdocs/snippets
COPY clusters clusters

# Required for navigation.instant (non-empty sitemap). Override at build time to match ingress host.
ARG MKDOCS_SITE_URL=https://docs.example.com
ARG DOCS_BUILD_SHA=unknown
ARG DOCS_BUILD_TIME=unknown
ARG DOCS_IMAGE_VERSION=unknown
ENV MKDOCS_SITE_URL=${MKDOCS_SITE_URL}
ENV DOCS_BUILD_SHA=${DOCS_BUILD_SHA}
ENV DOCS_BUILD_TIME=${DOCS_BUILD_TIME}
ENV DOCS_IMAGE_VERSION=${DOCS_IMAGE_VERSION}
# Avoid GitPython stderr noise when the plugin probes git during mkdocs build.
ENV GIT_PYTHON_REFRESH=quiet

COPY .git .git

RUN python scripts/collect_mkdocs.py \
    && mkdocs build -f mkdocs/mkdocs.generated.yml

FROM nginxinc/nginx-unprivileged:stable-alpine@sha256:df0e9edf92b8436ff797fe5a2cbfc66be1df775c113d322ccadf5c7f3100eda8

COPY --from=builder /src/mkdocs/site /usr/share/nginx/html

EXPOSE 8080
