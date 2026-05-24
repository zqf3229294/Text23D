FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        libgl1 \
        libglib2.0-0 \
        libxext6 \
        libxrender1 \
    && rm -rf /var/lib/apt/lists/*

RUN python -m pip install --no-cache-dir "cadquery>=2.5,<3"

WORKDIR /opt/text23d
COPY run_cadquery.py /opt/text23d/run_cadquery.py

ENTRYPOINT []
