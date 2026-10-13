FROM postgres:15-alpine
RUN apk add --no-cache python3
COPY backup.py restore.py /opt/backup/
USER 101:101
