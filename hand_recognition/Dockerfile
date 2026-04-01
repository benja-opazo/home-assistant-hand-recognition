ARG BUILD_FROM=python:3.12-slim
FROM $BUILD_FROM

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    libglib2.0-0 \
    libgl1 \
    libjpeg-dev \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN python3 -m pip install --no-cache-dir -r requirements.txt

COPY app/ .

COPY run.sh /run.sh
RUN chmod +x /run.sh

CMD ["/run.sh"]
