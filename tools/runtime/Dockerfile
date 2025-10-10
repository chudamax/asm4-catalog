FROM python:3.11-slim

RUN apt-get update && apt-get install -y --no-install-recommends ca-certificates && \
    rm -rf /var/lib/apt/lists/*

WORKDIR /app
COPY requirements.txt /app/
RUN python -m pip install --no-cache-dir --upgrade pip && \
    python -m pip install --no-cache-dir -r /app/requirements.txt

# Runtime + canonical models
COPY adapter_runtime /app/adapter_runtime
COPY models /app/models

# Stable entrypoint shared by all tools
ENTRYPOINT ["python","-m","adapter_runtime","--adapter"]
