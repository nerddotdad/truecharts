FROM python:3.14-slim@sha256:d3400aa122fa42cf0af0dbe8ec3091b047eac5c8f7e3539f7135e86d855dc015

WORKDIR /app
COPY bridge.py db.py filters.py hermes_client.py incidents.py message_format.py notifications.py ntfy_publish.py query_parser.py raise_rules.py settings.py ui.py /app/

ENV INCIDENT_DIR=/data/incidents \
    HTTP_PORT=8000

EXPOSE 8000
VOLUME ["/data/incidents"]

CMD ["python3", "/app/bridge.py"]
