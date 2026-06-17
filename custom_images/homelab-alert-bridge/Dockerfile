FROM python:3.14-slim@sha256:d7a925f9eb9639a93e455b9f12c167569358818c0f62b51b88edbc8fcf34c421

WORKDIR /app
COPY bridge.py db.py incidents.py message_format.py ntfy_publish.py ui.py /app/

ENV INCIDENT_DIR=/data/incidents \
    HTTP_PORT=8000

EXPOSE 8000
VOLUME ["/data/incidents"]

CMD ["python3", "/app/bridge.py"]
