ARG RUNTIME_IMAGE
FROM ${RUNTIME_IMAGE}

# RUN apt-get update && apt-get install -y --no-install-recommends ca-certificates curl && \
#     curl -sSfL https://github.com/projectdiscovery/httpx/releases/download/v1.6.1/httpx_1.6.1_linux_amd64.tar.gz \
#       | tar -xz -C /usr/local/bin httpx && \
#     chmod +x /usr/local/bin/httpx && \
#     rm -rf /var/lib/apt/lists/*

WORKDIR /app
COPY altdns_adapter.py /app/altdns_adapter.py
ENTRYPOINT ["python","-m","adapter_runtime","--adapter","altdns_adapter:AltDNSAdapter"]
