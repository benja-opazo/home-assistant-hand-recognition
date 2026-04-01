ARG BUILD_FROM=ghcr.io/home-assistant/amd64-base-python:3.11
FROM $BUILD_FROM

WORKDIR /app

# Install system dependencies for MediaPipe and OpenCV
RUN apk add --no-cache \
    libstdc++ \
    libgcc \
    glib \
    mesa-gl \
    jpeg-dev \
    zlib-dev \
    && rm -rf /var/cache/apk/*

COPY requirements.txt .
RUN python3 -m pip install --no-cache-dir -r requirements.txt

COPY app/ .

COPY run.sh /run.sh
RUN chmod +x /run.sh

CMD ["/run.sh"]
