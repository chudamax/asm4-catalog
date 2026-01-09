FROM python:3.11-slim

RUN apt-get update && apt-get install -y --no-install-recommends masscan ca-certificates \
  && rm -rf /var/lib/apt/lists/*

# Install local SDKs from the repo (works only if build context is repo root)
COPY tools/runtime/adapter_runtime /tmp/asm_adapter_runtime
COPY tools/runtime/wrappers  /tmp/asm_tool_wrappers
RUN pip install --no-cache-dir -e /tmp/asm_adapter_runtime -e /tmp/asm_tool_wrappers

WORKDIR /app

# Copy adapter code from repo path (not from tool-context root)
COPY tools/tools/masscan/masscan_adapter.py /app/masscan_adapter.py

ENTRYPOINT ["python", "-m", "asm_adapter_runtime.cli", "--adapter", "masscan_adapter:MasscanAdapter"]
