FROM python:3.14-slim@sha256:63a4c7f612a00f92042cbdcc7cdc6a306f38485af0a200b9c89de7d9b1607d15

WORKDIR /app
COPY bridge.py db.py filters.py hermes_client.py incidents.py message_format.py notifications.py ntfy_publish.py query_parser.py raise_rules.py settings.py ui.py /app/

ENV INCIDENT_DIR=/data/incidents \
    HTTP_PORT=8000

EXPOSE 8000
VOLUME ["/data/incidents"]

CMD ["python3", "/app/bridge.py"]
