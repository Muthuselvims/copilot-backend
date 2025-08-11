FROM debian:bookworm-slim

ENV DEBIAN_FRONTEND=noninteractive

RUN set -eux; \
    # Remove conflicting ODBC packages forcibly (ignore errors)
    dpkg -r --force-all libodbc2 libodbcinst2 unixodbc-common libodbc1 odbcinst1debian2 odbcinst unixodbc unixodbc-dev || true; \
    apt-get clean; rm -rf /var/lib/apt/lists/*; \
    \
    # Update and install base packages
    apt-get update; \
    apt-get install -y --no-install-recommends \
      curl gnupg apt-transport-https gcc g++ ca-certificates; \
    \
    # Setup Microsoft package repo key and list
    mkdir -p /etc/apt/keyrings; \
    curl -sSL https://packages.microsoft.com/keys/microsoft.asc | gpg --dearmor > /etc/apt/keyrings/microsoft.gpg; \
    echo "deb [arch=amd64 signed-by=/etc/apt/keyrings/microsoft.gpg] https://packages.microsoft.com/debian/11/prod bullseye main" > /etc/apt/sources.list.d/microsoft-prod.list; \
    \
    # Update and install unixodbc and msodbcsql17 freshly
    apt-get update; \
    apt-get install -y --no-install-recommends unixodbc unixodbc-dev; \
    ACCEPT_EULA=Y apt-get install -y msodbcsql17; \
    \
    apt-get clean; \
    rm -rf /var/lib/apt/lists/*
# Use official Debian Bookworm slim as base image
FROM debian:bookworm-slim

# Disable interactive prompts during package installs
ENV DEBIAN_FRONTEND=noninteractive

RUN set -eux; \
    # Force remove conflicting ODBC packages if installed, ignore errors
    dpkg -r --force-all libodbc2 libodbcinst2 unixodbc-common libodbc1 odbcinst1debian2 odbcinst unixodbc unixodbc-dev || true; \
    apt-get clean; rm -rf /var/lib/apt/lists/*; \
    \
    # Update package lists and install base dependencies
    apt-get update; \
    apt-get install -y --no-install-recommends \
      curl \
      gnupg \
      apt-transport-https \
      gcc \
      g++ \
      ca-certificates; \
    \
    # Add Microsoft package repository key and source
    mkdir -p /etc/apt/keyrings; \
    curl -sSL https://packages.microsoft.com/keys/microsoft.asc | gpg --dearmor > /etc/apt/keyrings/microsoft.gpg; \
    echo "deb [arch=amd64 signed-by=/etc/apt/keyrings/microsoft.gpg] https://packages.microsoft.com/debian/11/prod bullseye main" > /etc/apt/sources.list.d/microsoft-prod.list; \
    \
    # Update package lists to include MS repo
    apt-get update; \
    \
    # Install unixodbc and msodbcsql17 driver
    apt-get install -y --no-install-recommends unixodbc unixodbc-dev; \
    ACCEPT_EULA=Y apt-get install -y msodbcsql17; \
    \
    # Clean up apt cache to reduce image size
    apt-get clean; \
    rm -rf /var/lib/apt/lists/*

# You can add your app setup or CMD here if needed
# Install Python and pip, copy your app code, install python packages
RUN apt-get update && apt-get install -y python3 python3-pip

COPY requirements.txt .
RUN pip3 install -r requirements.txt

COPY . .

EXPOSE 8000

CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]