FROM python:3.12-slim@sha256:c845af9399020c7e562969a13689e929074a10fd057acd1b1fad06a2fb068e97

WORKDIR /app
COPY bridge.py /app/bridge.py

ENV INCIDENT_DIR=/data/incidents \
    HTTP_PORT=8000

EXPOSE 8000
VOLUME ["/data/incidents"]

CMD ["python3", "/app/bridge.py"]
