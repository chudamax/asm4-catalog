FROM python:3.11-slim

RUN apt-get update \
    && apt-get install -y --no-install-recommends masscan ca-certificates \
    && rm -rf /var/lib/apt/lists/*

RUN pip install --no-cache-dir asm-adapter-runtime==0.1.0 asm-tool-wrappers==0.1.0

WORKDIR /app
COPY masscan_adapter.py /app/masscan_adapter.py

ENTRYPOINT ["asm-adapter", "--adapter", "masscan_adapter:MasscanAdapter"]
