# BUILD_FROM must be declared before any FROM so it is in global scope
# and available to all FROM instructions in a multi-stage build.
ARG BUILD_FROM=ghcr.io/home-assistant/amd64-base-python:3.12-alpine3.21

# Stage 1: install Python packages on a glibc-based image so that
# manylinux wheels (mediapipe, opencv) can be resolved and installed.
FROM python:3.12-slim AS python-builder

RUN apt-get update && apt-get install -y --no-install-recommends \
    libglib2.0-0 \
    libgl1 \
    libjpeg-dev \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt /tmp/requirements.txt
RUN pip install --no-cache-dir --target=/packages -r /tmp/requirements.txt

# Stage 2: runtime on the HA Alpine base image.
# gcompat provides glibc ABI compatibility so the manylinux binaries
# copied from stage 1 can run on musl libc.
FROM $BUILD_FROM

RUN apk add --no-cache gcompat libstdc++ glib mesa-gl

WORKDIR /app

COPY --from=python-builder /packages /usr/local/lib/python3.12/site-packages

COPY app/ .

COPY run.sh /run.sh
RUN chmod +x /run.sh

CMD ["/run.sh"]
