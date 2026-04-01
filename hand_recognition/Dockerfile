# BUILD_FROM is passed by HA's builder; declared here to avoid warnings but
# we use python:3.12-slim directly so mediapipe/numpy glibc wheels work.
ARG BUILD_FROM=python:3.12-slim
FROM python:3.12-slim

RUN apt-get update && apt-get install -y --no-install-recommends \
    libglib2.0-0 \
    libgl1 \
    libjpeg-dev \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt /tmp/requirements.txt
RUN pip install --no-cache-dir -r /tmp/requirements.txt

WORKDIR /app

COPY app/ .

COPY run.sh /run.sh
RUN chmod +x /run.sh

CMD ["/run.sh"]
