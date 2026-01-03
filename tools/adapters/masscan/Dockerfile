FROM python:3.11-slim

# Install adapter runtime + wrappers straight from the repository sources. The
# build context now points at the shared ``tools`` directory, so we can copy the
# source trees directly instead of relying on pre-built wheels in ``_dist``.
COPY adapter_runtime /tmp/adapter_runtime
COPY wrappers /tmp/wrappers
RUN pip install --no-cache-dir /tmp/adapter_runtime /tmp/wrappers

# Install masscan binary (match existing image process)
RUN apt-get update \
    && apt-get install -y --no-install-recommends masscan ca-certificates \
    && rm -rf /var/lib/apt/lists/*

# Adapter code
WORKDIR /app
COPY adapters/masscan_only/adapter/ /app/adapter/

ENTRYPOINT ["asm-adapter", "--adapter", "adapter.masscan_adapter:MasscanAdapter"]
