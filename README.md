# ASM Catalog Tooling Specification (v1) — Single Repo with Tools + Playbooks + Rules

Use this document as the **single source of truth** for how to add new content to the ASM catalog repo.
It is written to be **Codex-friendly**: clear file locations, required fields, and copy/paste templates.

Assumptions:
- You want to keep **tools inside the `asm-catalog` repo** (no separate tools repo).
- Tools are executed as **container images**.
- Tools implement the existing **`asm_adapter_runtime` BaseAdapter contract** (runtime is a Python package).

---

## 1) What the catalog repo contains

The catalog repo is a **content bundle** that the platform syncs (Git → DB). It may include:

- **Tools**: tool manifests + Dockerfiles + adapter code (and optionally wrappers).
- **Profiles**: named parameter presets for a tool version.
- **Tasks**: binding of “tool profile + materializer + defaults”.
- **Playbooks**: orchestration graphs (bind tasks to scope rules and promotion rules).
- **Rules**:
  - **scope** rules: select inventory objects for a playbook binding
  - **promotion** rules: decide which produced events get promoted into inventory
  - **detection** rules: queries that create findings
- **Resources**: auxiliary files referenced by tools/tasks (wordlists, templates, etc.).
- (Optional) **runtime image** build assets: shared base image used by all tools.

---

## 2) Repository layout (required)

This is the **required directory structure**. Add new tools/content by copying the templates below.

```text
asm-catalog/
  README.md

  # Orchestration
  playbooks/
    <playbook>.yaml

  tasks/
    <task>.yaml

  profiles/
    <tool>-<profile>.yaml

  # Policy & logic
  rules/
    scope/
      <scope_rule>.yaml
    promotion/
      <promotion_rule>.yaml
    detection/
      <detection_rule>.yaml

  # Optional external files referenced by tools/tasks
  resources/
    <resource_group>/
      resource.yaml
      ...files...

  # Tools
  tools/
    runtime/                       # runtime package used by tools (BaseAdapter, models)
      adapter_runtime/
      wrappers/
    tools/
      <tool>/
        manifest.yaml              # REQUIRED tool manifest (tool@v1)
        Dockerfile                 # REQUIRED image build recipe
        <tool>_adapter.py          # REQUIRED adapter entrypoint (BaseAdapter subclass)

        # OPTIONAL (recommended for real tools)
        models/                    # tool-specific helper models/parsers (not platform models)
          __init__.py
          ...
        fixtures/                  # local test data (safe targets, sample outputs)
          inputs.txt
          inputs.manifest.json
          ...
        tests/                     # pytest tests
          test_smoke.py
          test_parse.py
```

**Naming rules**
- Tool directory name: `tools/tools/<tool>/` (lowercase, no spaces).
- Adapter entry file name: `<tool>_adapter.py`.
- Adapter class name: `<ToolTitle>Adapter` (PascalCase).
- Tool manifest name: exactly `manifest.yaml`.

---

## 3) Platform lifecycle: sync → publish → plan → launch → ingest

### 3.1 Catalog sync (Git → DB)
The platform periodically syncs this repo:
- reads tool manifests, profiles, tasks, playbooks, rules, resources
- stores them as DB records tied to a repo + commit + path

### 3.2 Publish (build/push tool images + pin digests)
Publishing turns tool source into a trusted runnable artifact:
- build an image using the tool’s `manifest.yaml` build section
- push image to registry
- record the immutable digest reference `repo/name@sha256:...`
- update either:
  - the tool manifest (`runtime.image_digest`) **or**
  - a DB field (recommended if you don’t want Git commits during publish)

**Policy recommendation:** run by digest in production; allow tag-only in dev.

### 3.3 Plan + launch
Planner writes batch artifacts:
- `inputs.txt` (targets)
- `inputs.manifest.json` (parameters/resources/profile/tool metadata)
- presigned URLs for tool containers

Launcher starts the tool container with env vars:
- `TENANT_ID`, `RUN_ID`, `BATCH_ID`
- `INPUTS_URL`
- `RESOURCES_MANIFEST_URL` (points to `inputs.manifest.json`)
- `OUTPUT_URL` (presigned write URL for `events.jsonl.gz`)
- `SIGNAL_URL` (optional; HTTP sink for progress/completion signals)

### 3.4 Ingest
Ingestor downloads `events.jsonl.gz`, validates JSONL envelopes, and indexes events.

---

## 4) Tool Manifest v1 (`tool@v1`) — REQUIRED

Tool manifests are YAML files at:
- `tools/tools/<tool>/manifest.yaml`

### 4.1 Required fields

```yaml
apiVersion: tool@v1
tool: "<tool>"
version: "<tool-version>"          # your adapter/tool release version
description: "<human description>"

io:
  inputKind: <kind>                # see allowed values below
  produces:
    - event_type: "<event.type>"
      schema: "<schema-id>"

constraints:
  max_batch_size: <int>

params:                            # list of param definitions (optional; recommended)
  - name: <param_name>
    type: <type>                   # string|integer|number|boolean|array|object
    required: <bool>
    default: <value>
    description: "<text>"
    minimum: <num>                 # optional
    maximum: <num>                 # optional
    enum: [ ... ]                  # optional
    pattern: "<regex>"             # optional for strings
    items: { type: <type> }        # optional for arrays

contracts:
  resources: []                    # declared external resources (optional)
  context: []                      # declared context keys (optional)

runtime:
  image: "<repo/name:tag>"         # tag is OK for dev
  image_digest: "sha256:..."       # REQUIRED for production policy
  cpu_millis: 500
  memory_mb: 256
  timeout_seconds: 900             # recommended

build:
  dockerfile: "Dockerfile"
  context: "."
  args: {}                         # optional build args (e.g., RUNTIME_IMAGE)
```

### 4.2 Allowed `io.inputKind` values
Use the smallest correct type:
- `ip` — single IP per line
- `cidr` — CIDR per line
- `host` — hostname/FQDN per line
- `domain` — domain per line (usually same as host but conceptually distinct)
- `url` — URL per line
- `hostport` — `host:port` per line

### 4.3 Param definition rules
- Each `params[]` entry MUST have: `name`, `type`, `required`, `description`.
- If `required: true`, do **not** provide `default` unless the default is safe.
- If `type: array`, include `items`.
- Prefer **strings** for CLI-ish values (ports/ranges), integers for counts/rates.

---

## 5) Example tool: Nmap (complete minimal set)

### 5.1 `tools/tools/nmap/manifest.yaml`

```yaml
apiVersion: tool@v1
tool: "nmap"
version: "1.0.0"
description: "Nmap scanner emitting network.service events"

io:
  inputKind: host
  produces:
    - event_type: "network.service"
      schema: "events/network_service@v1"

constraints:
  max_batch_size: 5000

params:
  - name: ports
    type: string
    required: false
    default: "443"
    description: "Ports or ranges (nmap -p syntax), e.g. 80,443,8000-8100"

  - name: scan_type
    type: string
    required: false
    default: "connect"
    enum: ["connect", "syn"]
    description: "connect uses -sT, syn uses -sS (requires NET_RAW/NET_ADMIN)"

  - name: timing
    type: string
    required: false
    default: "T3"
    enum: ["T0","T1","T2","T3","T4","T5"]
    description: "Nmap timing template"

  - name: scripts
    type: string
    required: false
    description: "Optional NSE scripts selector, e.g. default or http-title,http-headers"

  - name: extra_args
    type: array
    items: { type: string }
    required: false
    description: "Extra CLI args appended at end (use sparingly)"

contracts:
  resources: []
  context: []

runtime:
  image: "nmap:1.0.0"
  image_digest: "sha256:REPLACE_AFTER_PUBLISH"
  cpu_millis: 500
  memory_mb: 512
  timeout_seconds: 1800

build:
  dockerfile: "Dockerfile"
  context: "."
  args:
    RUNTIME_IMAGE: "registry.example.com/asm/tool-runtime@sha256:REPLACE"
```

### 5.2 `tools/tools/nmap/Dockerfile`

Install the runtime package inside the tool image:

```dockerfile
FROM python:3.11-slim

RUN apt-get update \
  && apt-get install -y --no-install-recommends nmap ca-certificates \
  && rm -rf /var/lib/apt/lists/*

RUN pip install --no-cache-dir asm-adapter-runtime==0.1.0

WORKDIR /app
COPY nmap_adapter.py /app/nmap_adapter.py

ENTRYPOINT ["asm-adapter", "--adapter", "nmap_adapter:NmapAdapter"]
```

### 5.3 `tools/tools/nmap/nmap_adapter.py` (skeleton)

```python
from __future__ import annotations

import subprocess
from pathlib import Path
from typing import List, Optional

from asm_adapter_runtime import BaseAdapter, BatchConfig, Heartbeat

# Prefer canonical models from asm_adapter_runtime.models when available
# from asm_adapter_runtime.models import NetworkService

class NmapAdapter(BaseAdapter):
    TOOL = "nmap"
    TOOL_VERSION = "1.0.0"
    PRODUCES = ("network.service",)

    @property
    def binary_path(self) -> str:
        return "/usr/bin/nmap"

    def build_cmd(self, targets: List[str], cfg: BatchConfig, workdir: Path) -> Optional[List[str]]:
        # Write targets file
        targets_file = workdir / "targets.txt"
        targets_file.write_text("\n".join(targets) + ("\n" if targets else ""), encoding="utf-8")

        params = cfg.parameters or {}
        ports = params.get("ports") or "443"
        scan_type = params.get("scan_type") or "connect"
        timing = params.get("timing") or "T3"
        scripts = params.get("scripts")
        extra_args = params.get("extra_args") or []

        out_xml = workdir / "nmap.xml"

        cmd = [self.binary_path, f"-{timing}", "-p", str(ports), "-oX", str(out_xml), "-iL", str(targets_file)]

        if scan_type == "syn":
            cmd += ["-sS"]
        else:
            cmd += ["-sT"]

        if scripts:
            cmd += ["--script", str(scripts)]

        cmd += [str(x) for x in extra_args]
        return cmd

    def parse_tool_output(self, line: str, emit, hb: Heartbeat) -> None:
        # For this skeleton: do nothing (we parse the XML file after run in generate()).
        # If you stream JSON output, parse per line and emit events here.
        return

    def generate(self, targets: List[str], cfg: BatchConfig, emit, hb: Heartbeat) -> int:
        # Alternative pattern: run tool yourself and parse output file.
        # If you implement build_cmd() above, you can omit generate() entirely
        # and rely on BaseAdapter to run the cmd and call parse_tool_output().
        #
        # To keep variance low, choose ONE pattern per tool:
        # - build_cmd + parse_tool_output
        # - OR generate (run + parse)
        return 0
```

**Pick ONE adapter pattern:**
- Pattern A (common): implement `build_cmd()` and `parse_tool_output()`
- Pattern B: implement `generate()` only

Do not mix both unless you know exactly how the runtime calls them.

---

## 6) Profiles — REQUIRED for orchestration

Profiles live at:
- `profiles/<tool>-<profile>.yaml`

A profile is a named parameter bundle for a specific tool version.

```yaml
slug: "nmap-safe"
version: 1
tool: "nmap"
tool_version: "1.0.0"

params:
  ports: "443"
  scan_type: "connect"
  timing: "T3"
```

Rules:
- `slug` must be unique.
- Keep profiles conservative by default (“safe” should not be aggressive).

---

## 7) Tasks — REQUIRED if you want the platform to run it automatically

Tasks live at:
- `tasks/<task>.yaml`

A task binds:
- a tool profile
- a materializer (how to turn inventory items into tool inputs)
- defaults (batch sizing, concurrency, coverage TTL)

Example:

```yaml
schemaVersion: asm/v1
kind: Task

metadata:
  slug: nmap.scan
  version: 1
  name: "Nmap Scan"
  description: "Scan targets for open services using the Nmap adapter."

materialize:
  input: host
  materializer: host.default@1

tool:
  profile: nmap-safe@1

coverageDefaults:
  ttl: 14d
  variant: host

constraintsDefault:
  maxBatchSize: 5000
  maxConcurrency: 8
```

---

## 8) Playbooks — REQUIRED if you want it in a workflow

Playbooks live at:
- `playbooks/<playbook>.yaml`

Example:

```yaml
schemaVersion: asm/v1
kind: Playbook

metadata:
  slug: nmap_test
  version: "1"
  name: "nmap_test"

bindings:
  - idx: 0
    alias: nmap.scan
    task: nmap.scan@1
    scopeMap:
      InvHost: tenant_all_hosts@1
    promotionRuleset: promote_network_services@1
```

---

## 9) Rules

### 9.1 Scope rules (`rules/scope/*.yaml`)
Select which inventory objects become inputs.

```yaml
slug: "tenant_all_hosts"
subject_type: "InvHost"
conditions:
  all: []
```

### 9.2 Promotion rules (`rules/promotion/*.yaml`)
Decide which produced events get promoted into inventory.

```yaml
slug: "promote_network_services"
subject_type: "network.service@v1"
conditions:
  all: []
exceptions:
  any: []
```

### 9.3 Detection rules (`rules/detection/*.yaml`)
Queries that generate findings.

```yaml
name: "Detect SSH on Public IPs"
query_kql: event.port == 22 and event.protocol == "tcp" and event.is_public == true
severity: high
title: "SSH exposed to the internet"
description: "Port 22 open on a public host."
tenant_id: null
```

---

## 10) Resources

Resources live at:
- `resources/<group>/resource.yaml` plus files

Example:

```yaml
name: "nmap-safe-scripts"
version: 1
files:
  - path: "safe_scripts.txt"
    sha256: "REPLACE"
```

**How tools receive resources**
- The platform includes resources as downloadable items in `inputs.manifest.json` (see below).
- The adapter runtime downloads them into `<workdir>/resources/<filename>` and (optionally) extracts archives.

---

## 11) Runtime contract (how containers run)

### 11.1 Environment variables (set by Launcher)

Required:
- `TENANT_ID`
- `RUN_ID`
- `BATCH_ID`
- `INPUTS_URL` — presigned URL to `inputs.txt` (newline-separated)
- `RESOURCES_MANIFEST_URL` — presigned URL to `inputs.manifest.json`
- `OUTPUT_URL` — presigned write URL for `events.jsonl.gz`

Optional:
- `SIGNAL_URL` — HTTP sink for signals
- `OCS_PREFIX` — object storage prefix for debugging
- `TOOL_IMAGE_DIGEST` — if available; runtime may include it in event envelopes
- `HEARTBEAT_SECONDS` — progress heartbeat interval
- `ADAPTER_PRESERVE_WORKDIR=1` — keep temp directory for debugging

### 11.2 `inputs.txt`
Plain text file:
- one target per line
- trimmed; empty lines ignored
- must match tool manifest `io.inputKind`

### 11.3 `inputs.manifest.json` (what `RESOURCES_MANIFEST_URL` points to)

Minimum fields that adapters need:

```json
{
  "tool": "nmap",
  "tool_version": "1.0.0",
  "parameters": { "ports": "443", "timing": "T3" },
  "resources": [
    {
      "name": "nmap-safe-scripts",
      "url": "https://.../safe_scripts.txt",
      "sha256": "...",
      "filename": "safe_scripts.txt",
      "extract": false
    }
  ],

  "tool_profile": { "slug": "nmap-safe", "version": 1 }
}
```

Rules:
- Adapters MUST ignore unknown fields.
- `parameters` should match the tool manifest `params[]` definitions.
- `resources[]` can be empty.

### 11.4 Tool output: `events.jsonl.gz`
Adapters must produce a gzipped JSON Lines file where each line is an **event envelope**.

Event envelope format:

```json
{
  "tool": "nmap",
  "tool_version": "1.0.0",
  "run_id": "r1",
  "batch_id": "b1",
  "event_type": "network.service",
  "timestamp": "2026-01-03T12:34:56Z",
  "payload": { "ip": "203.0.113.10", "port": 443, "protocol": "tcp" },
  "tool_image_digest": "sha256:..."
}
```

**Required keys:**
- `tool`, `tool_version`, `run_id`, `batch_id`, `event_type`, `timestamp`, `payload`

---

## 12) Signals (optional but recommended)

If `SIGNAL_URL` is provided, adapters may POST JSON messages.

Supported types:
- `progress@v1`
- `results_ready@v1`

Example progress message:
```json
{ "type": "progress@v1", "run_id": "r1", "batch_id": "b1", "seen": 1000, "emitted": 42 }
```

Example completion message:
```json
{ "type": "results_ready@v1", "run_id": "r1", "batch_id": "b1", "events_blob": "runs/.../events.jsonl.gz", "sha256": "..." }
```

---

## 13) Publishing spec (build + push + pin digest)

### 13.1 Build context and Docker limitations
Docker can only `COPY` files inside the build context.

In this repo layout:
- tool build context is usually `tools/tools/<tool>/`
- shared runtime image is built from `tools/runtime/`

### 13.2 Recommended publishing algorithm
For a tool `<tool>` version `<ver>`:
1) Build/push runtime base image (if you use it):
   - `docker build -t <registry>/tool-runtime:<tag> tools/runtime`
   - push and obtain digest
2) Build/push tool image:
   - `docker build --build-arg RUNTIME_IMAGE=<registry>/tool-runtime@sha256:... -t <registry>/<ns>/<tool>:<ver> tools/tools/<tool>`
   - push and obtain digest
3) Pin digest:
   - write `runtime.image_digest: sha256:...` in `tools/tools/<tool>/manifest.yaml` OR store in DB

**Policy recommendation:** refuse production runs if digest is missing.

---

## 14) Local testing (without the platform)

### 14.1 Build locally
From repo root:

```bash
docker build -t asm/tool-runtime:dev tools/runtime
docker build --build-arg RUNTIME_IMAGE=asm/tool-runtime:dev -t asm/nmap:dev tools/tools/nmap
```

### 14.2 Run locally using `file://` URLs
Create a local work dir:

```bash
mkdir -p /tmp/asm-nmap-local
printf "asm-testapp.com\n" > /tmp/asm-nmap-local/inputs.txt

cat > /tmp/asm-nmap-local/inputs.manifest.json <<'JSON'
{
  "tool": "nmap",
  "tool_version": "1.0.0",
  "parameters": { "ports": "443", "scan_type": "connect", "timing": "T3" },
  "resources": [],
  "tool_profile": { "slug": "nmap-safe", "version": 1 }
}
JSON
```

Run the container:

```bash
docker run --rm -v /tmp/asm-nmap-local:/work \
  -e TENANT_ID=local \
  -e RUN_ID=local-run \
  -e BATCH_ID=local-batch \
  -e INPUTS_URL=file:///work/inputs.txt \
  -e RESOURCES_MANIFEST_URL=file:///work/inputs.manifest.json \
  -e OUTPUT_URL=file:///work/events.jsonl.gz \
  asm/nmap:dev
```

Inspect output:

```bash
gzip -dc /tmp/asm-nmap-local/events.jsonl.gz | head
```

### 14.3 Tools that require raw sockets
If you use SYN scans or raw packets, run with caps:

```bash
docker run --rm --cap-add NET_RAW --cap-add NET_ADMIN -v /tmp/asm-nmap-local:/work \
  -e INPUTS_URL=file:///work/inputs.txt \
  -e RESOURCES_MANIFEST_URL=file:///work/inputs.manifest.json \
  -e OUTPUT_URL=file:///work/events.jsonl.gz \
  asm/nmap:dev
```

---

## 15) Codex tool template (copy/paste, minimal variance)

To create a new tool `<tool>` version `<ver>`:

### 15.1 Create directories

```text
tools/tools/<tool>/
  manifest.yaml
  Dockerfile
  <tool>_adapter.py
  fixtures/
    inputs.txt
    inputs.manifest.json
```

### 15.2 `manifest.yaml` template

```yaml
apiVersion: tool@v1
tool: "<tool>"
version: "<ver>"
description: "<one sentence>"

io:
  inputKind: <host|ip|cidr|domain|url|hostport>
  produces:
    - event_type: "<event.type>"
      schema: "<schema-id>"

constraints:
  max_batch_size: 1000

params:
  - name: extra_args
    type: array
    items: { type: string }
    required: false
    description: "Extra CLI args appended at end (use sparingly)."

contracts:
  resources: []
  context: []

runtime:
  image: "<tool>:<ver>"
  image_digest: "sha256:REPLACE_AFTER_PUBLISH"
  cpu_millis: 500
  memory_mb: 256
  timeout_seconds: 900

build:
  dockerfile: "Dockerfile"
  context: "."
  args:
    RUNTIME_IMAGE: "registry.example.com/asm/tool-runtime@sha256:REPLACE"
```

### 15.3 `Dockerfile` template

```dockerfile
ARG RUNTIME_IMAGE
FROM ${RUNTIME_IMAGE}

# Install tool binary here (apt/apk/curl/unzip/etc.)
# RUN ...

WORKDIR /app
COPY <tool>_adapter.py /app/<tool>_adapter.py

ENTRYPOINT ["asm-adapter", "--adapter", "<tool>_adapter:<ToolTitle>Adapter"]
```

### 15.4 `<tool>_adapter.py` template (Pattern A: CLI + streaming parse)

```python
from __future__ import annotations

from pathlib import Path
from typing import List, Optional

from asm_adapter_runtime import BaseAdapter, BatchConfig, Heartbeat

class <ToolTitle>Adapter(BaseAdapter):
    TOOL = "<tool>"
    TOOL_VERSION = "<ver>"
    PRODUCES = ("<event.type>",)

    @property
    def binary_path(self) -> str:
        return "/usr/local/bin/<tool>"

    def build_cmd(self, targets: List[str], cfg: BatchConfig, workdir: Path) -> Optional[List[str]]:
        # Write targets
        targets_file = workdir / "targets.txt"
        targets_file.write_text("\n".join(targets) + ("\n" if targets else ""), encoding="utf-8")

        params = cfg.parameters or {}
        extra_args = params.get("extra_args") or []

        # Build command
        cmd = [self.binary_path]
        # cmd += ["--targets", str(targets_file)]
        cmd += [str(x) for x in extra_args]
        return cmd

    def parse_tool_output(self, line: str, emit, hb: Heartbeat) -> None:
        # Parse each output line and emit events.
        # emit("<event.type>", {"field": "value"})
        return
```

### 15.5 `fixtures/inputs.txt` template
Use your owned target for real integration tests:

```text
asm-testapp.com
```

### 15.6 `fixtures/inputs.manifest.json` template

```json
{
  "tool": "<tool>",
  "tool_version": "<ver>",
  "parameters": {},
  "resources": [],
  "tool_profile": { "slug": "<tool>-default", "version": 1 }
}
```

---

## 16) Checklist for “adding a new tool end-to-end”

- [ ] Create `tools/tools/<tool>/manifest.yaml` (tool@v1)
- [ ] Create `tools/tools/<tool>/Dockerfile`
- [ ] Create `tools/tools/<tool>/<tool>_adapter.py`
- [ ] Create at least one profile `profiles/<tool>-default.yaml`
- [ ] Create a task `tasks/<tool>.scan.yaml` referencing that profile
- [ ] Add (or update) a playbook binding for scope + promotion rules
- [ ] Publish image and pin digest
- [ ] Run locally with file URLs and verify `events.jsonl.gz`

---

## 17) Operational safety rules (must-follow)

- Never scan targets not present in `inputs.txt`.
- Default profiles should be conservative (rate/ports).
- If a tool needs raw sockets, declare it via runtime/run instructions and run with caps only when necessary.
- Emit only the event types you declare in the tool manifest `io.produces[]`.
- Always exit non-zero on fatal errors; exit zero for “no findings”.
