# Use official slim Python base
FROM python:3.10-slim

# Environment vars for Microsoft SQL Server driver
ENV ACCEPT_EULA=Y
ENV DEBIAN_FRONTEND=noninteractive

# Install system dependencies and ODBC driver
RUN apt-get update && \
    apt-get install -y --no-install-recommends \
        curl \
        gnupg2 \
        apt-transport-https \
        unixodbc \
        unixodbc-dev \
        gcc \
        g++ \
        ca-certificates \
        software-properties-common && \
    curl https://packages.microsoft.com/keys/microsoft.asc | gpg --dearmor > microsoft.gpg && \
    install -o root -g root -m 644 microsoft.gpg /etc/apt/trusted.gpg.d/ && \
    rm microsoft.gpg && \
    curl https://packages.microsoft.com/config/debian/11/prod.list > /etc/apt/sources.list.d/mssql-release.list && \
    apt-get update && \
    ACCEPT_EULA=Y apt-get install -y msodbcsql17 && \
    apt-get clean && \
    rm -rf /var/lib/apt/lists/*

# Set working directory
WORKDIR /app

# Copy only requirements first for caching
COPY requirements.txt .

# Install Python dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Copy rest of the code
COPY . .

# Expose FastAPI port (Render uses 10000+)
EXPOSE 8000

# Start FastAPI with uvicorn (adjust if your main FastAPI app is elsewhere)
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
