FROM python:3.12-slim@sha256:090ba77e2958f6af52a5341f788b50b032dd4ca28377d2893dcf1ecbdfdfe203

WORKDIR /app
COPY bridge.py /app/bridge.py

ENV INCIDENT_DIR=/data/incidents \
    HTTP_PORT=8000

EXPOSE 8000
VOLUME ["/data/incidents"]

CMD ["python3", "/app/bridge.py"]
