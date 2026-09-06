# =============================================================================
# Debian-based Home Assistant development container.
#
# The official `homeassistant/home-assistant` image is built on Alpine Linux
# (musl libc), which the VS Code Server (Node.js) cannot run on. This image
# uses Debian (glibc) and installs Home Assistant Core via pip, so the custom
# component can be developed live inside the container (mounted at
# /config/custom_components/universal_notifier).
# =============================================================================

FROM mcr.microsoft.com/devcontainers/python:3.13-bookworm

# System libraries used by Home Assistant Core and common integrations.
RUN apt-get update \
    && apt-get install -y --no-install-recommends \
    ffmpeg \
    libturbojpeg0 \
    libjpeg62-turbo \
    libxml2 \
    libxslt1.1 \
    tzdata \
    && rm -rf /var/lib/apt/lists/*

# Tooling: uv (project dependency management) + Home Assistant Core (latest stable).
# Home Assistant is installed system-wide so the `hass` entry point is on PATH;
# the project's own test dependencies are managed separately by `uv sync`.
#
# NOTE: `pip install homeassistant` installs CORE ONLY — no integration deps.
# La dev config NON usa `default_config:` (troppe integrazioni con deps pip
# pesanti), ma una lista esplicita di integrazioni core-only. L'unica
# requirement extra è il frontend: il pacchetto PyPI `home-assistant-frontend`
# (che fornisce il modulo importabile `hass_frontend`).
RUN pip install --no-cache-dir \
    uv \
    homeassistant \
    home-assistant-frontend

WORKDIR /workspace

