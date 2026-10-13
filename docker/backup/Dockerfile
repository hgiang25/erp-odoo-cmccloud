FROM postgres:15-alpine
ARG BOTO3_VERSION=1.43.112
RUN apk add --no-cache python3 py3-pip \
    && python3 -m pip install --break-system-packages --no-cache-dir "boto3==${BOTO3_VERSION}"
COPY backup.py restore.py /opt/backup/
USER 101:101
