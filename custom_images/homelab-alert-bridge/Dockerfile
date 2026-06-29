FROM python:3.14-slim@sha256:b877e50bd90de10af8d82c57a022fc2e0dc731c5320d762a27986facfc3355c1

WORKDIR /app
COPY bridge.py db.py filters.py hermes_client.py incidents.py message_format.py notifications.py ntfy_publish.py query_parser.py raise_rules.py settings.py ui.py /app/

ENV INCIDENT_DIR=/data/incidents \
    HTTP_PORT=8000

EXPOSE 8000
VOLUME ["/data/incidents"]

CMD ["python3", "/app/bridge.py"]
