# Build static docs from documentation/ + clusters/ helm manifests (repo root context).
FROM python:3.14-slim@sha256:b877e50bd90de10af8d82c57a022fc2e0dc731c5320d762a27986facfc3355c1 AS builder

WORKDIR /src

COPY mkdocs/requirements.txt mkdocs/requirements.txt
RUN pip install --no-cache-dir -r mkdocs/requirements.txt

COPY scripts/collect_mkdocs.py scripts/collect_mkdocs.py
COPY scripts/doc_metadata.py scripts/doc_metadata.py
COPY scripts/doc_paths.py scripts/doc_paths.py
COPY scripts/helmrelease_docs.py scripts/helmrelease_docs.py
COPY scripts/runbook_index.py scripts/runbook_index.py
COPY mkdocs/mkdocs.base.yml mkdocs/mkdocs.base.yml
COPY mkdocs/templates mkdocs/templates
COPY mkdocs/snippets mkdocs/snippets
COPY documentation documentation
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

# GitHub Actions / BuildKit do not send .git in the build context. Per-page dates and
# build SHA come from collect_mkdocs (DOCS_BUILD_* args + freshness banners).
RUN python scripts/collect_mkdocs.py \
    && mkdocs build -f mkdocs/mkdocs.generated.yml

FROM nginxinc/nginx-unprivileged:stable-alpine@sha256:b3f2436575bd5be7386518084d842dac414ab4962712afa31e99e0942a56e3b2

COPY --from=builder /src/mkdocs/site /usr/share/nginx/html

EXPOSE 8080
