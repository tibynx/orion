## Build stage
FROM python:3.14-alpine AS build-stage

# set environment
WORKDIR /app

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
ENV PATH="/app/venv/bin:$PATH"

# set venv and copy requirements
RUN python -m venv /app/venv
COPY requirements.txt .

# install packages
RUN pip install --no-cache-dir -r requirements.txt

## Runtime stage
FROM python:3.14-alpine AS runtime-stage

# set labels
ARG BUILD_DATE
ARG VERSION
LABEL org.opencontainers.image.authors="tibynx (https://github.com/tibynx)"
LABEL org.opencontainers.image.created="${BUILD_DATE}"
LABEL org.opencontainers.image.version="${VERSION}"
LABEL org.opencontainers.image.title="Orion"
LABEL org.opencontainers.image.description="A Discord bot with server management and utility functions."
LABEL org.opencontainers.image.source="https://github.com/tibynx/orion"
LABEL org.opencontainers.image.url="https://github.com/tibynx/orion/packages"
LABEL org.opencontainers.image.licenses="GPL-3.0"
LABEL org.opencontainers.image.base.name="python:3.14-alpine"
LABEL org.opencontainers.image.base.documentation="https://hub.docker.com/_/python"

# install ffmpeg and opus for voice support
RUN apk add --no-cache ffmpeg opus

# set environment
WORKDIR /app

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
ENV PATH="/app/venv/bin:$PATH"

# copy files from build-stage
COPY --from=build-stage /app/venv /app/venv
COPY . .

# set volume for logs
VOLUME ["/app/logs"]

# run the app
CMD ["python", "main.py"]
