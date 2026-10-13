FROM odoo:17.0
USER root
ARG OCA_QUEUE_REF=983b6adc1aa780c3d69247cd2d5cadc91bcffe82
RUN apt-get update && apt-get install -y --no-install-recommends git \
    && mkdir -p /opt/oca/queue \
    && git -C /opt/oca/queue init \
    && git -C /opt/oca/queue remote add origin https://github.com/OCA/queue.git \
    && git -C /opt/oca/queue fetch --depth=1 origin "$OCA_QUEUE_REF" \
    && git -C /opt/oca/queue checkout --detach FETCH_HEAD \
    && test "$(git -C /opt/oca/queue rev-parse HEAD)" = "$OCA_QUEUE_REF" \
    && rm -rf /opt/oca/queue/.git /var/lib/apt/lists/*
COPY render_config.py init_db.py /opt/odoo-k8s/
USER odoo
# Inherit /entrypoint.sh, including wait-for-psql and Secret-derived DB args.
