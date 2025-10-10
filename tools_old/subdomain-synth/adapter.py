#!/usr/bin/env python3
import os, io, json, gzip, time, hashlib, requests
from datetime import datetime, timezone

TENANT_ID   = os.getenv("TENANT_ID") or ""
RUN_ID      = os.getenv("RUN_ID") or ""
BATCH_ID    = os.getenv("BATCH_ID") or ""
OCS_PREFIX  = os.getenv("OCS_PREFIX") or ""     # e.g., runs/<run>/batches/<batch>/
INPUTS_URL  = os.getenv("INPUTS_URL")           # presigned GET (Planner/Launcher)
RES_MAN_URL = os.getenv("RESOURCES_MANIFEST_URL")  # not used here, but provided
SIGNAL_URL  = os.getenv("SIGNAL_URL")           # where we POST progress/results
OUTPUT_URL  = os.getenv("OUTPUT_URL")           # presigned PUT of events.jsonl.gz
TOOL        = "subdomain-synth"
TOOL_VERSION= "0.1.0"

def iso_now():
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

def post_signal(payload: dict):
    if not SIGNAL_URL: return
    try:
        requests.post(SIGNAL_URL, json=payload, timeout=20)
    except Exception:
        pass

def main():
    # 1) Download inputs.txt
    r = requests.get(INPUTS_URL, timeout=60); r.raise_for_status()
    roots = [ln.strip() for ln in r.text.splitlines() if ln.strip()]
    total = len(roots)

    # Optional prefixes param via env (Launcher materializes profile params as envs if desired)
    prefixes = os.getenv("PREFIXES_JSON")
    if prefixes:
        try:
            prefixes = json.loads(prefixes)
            if not isinstance(prefixes, list): prefixes = None
        except Exception:
            prefixes = None
    if not prefixes:
        prefixes = ["test1", "test2", "test"]  # manifest default

    post_signal({
        "kind":"progress@v1",
        "tenant_id":TENANT_ID,"run_id":RUN_ID,"batch_id":BATCH_ID,
        "tool":TOOL,"tool_version":TOOL_VERSION,
        "processed_targets":0,"emitted_docs":0,"phase":"start","at":iso_now()
    })

    # 2) Generate events.jsonl.gz (envelope@v1 lines)
    out = io.BytesIO()
    gz = gzip.GzipFile(fileobj=out, mode="wb")
    emitted = 0

    for i, root in enumerate(roots, 1):
        for p in prefixes:
            sub = f"{p}.{root}".lower()
            envelope = {
                "tool": TOOL,
                "tool_version": TOOL_VERSION,
                "run_id": RUN_ID,
                "batch_id": BATCH_ID,
                "event_type": "dns.domain",          # <— unified type
                "timestamp": iso_now(),
                "payload": {
                    "name":   sub,                   # full FQDN
                    "root":   root.lower(),          # registrable root
                    "kind":   "subdomain",           # discriminator
                    "parent": root.lower()
                }
            }
            line = (json.dumps(envelope) + "\n").encode("utf-8")
            gz.write(line)
            emitted += 1

        if i % 500 == 0 or i == total:
            post_signal({
                "kind":"progress@v1",
                "tenant_id":TENANT_ID,"run_id":RUN_ID,"batch_id":BATCH_ID,
                "tool":TOOL,"tool_version":TOOL_VERSION,
                "processed_targets":i,"emitted_docs":emitted,"phase":"generate","at":iso_now()
            })

    gz.close()
    out.seek(0)

    # 3) Upload to ObjectStore with presigned PUT
    if not OUTPUT_URL:
        # As a safety net, still announce results (control-plane may pull from OCS_PREFIX by convention)
        sha = hashlib.sha256(out.getvalue()).hexdigest()
        post_signal({
            "kind":"results_ready@v1",
            "tenant_id":TENANT_ID,"run_id":RUN_ID,"batch_id":BATCH_ID,
            "tool":TOOL,"tool_version":TOOL_VERSION,
            "doc_count": emitted,
            "events_blob": f"{OCS_PREFIX}events.jsonl.gz",
            "events_sha256": sha,
            "created_at": iso_now()
        })
        return 0

    resp = requests.put(OUTPUT_URL, data=out.getvalue(), headers={"Content-Type":"application/gzip"}, timeout=120)
    resp.raise_for_status()

    # 4) Compute sha256 for integrity & send results_ready
    sha = hashlib.sha256(out.getvalue()).hexdigest()
    post_signal({
        "kind":"results_ready@v1",
        "tenant_id":TENANT_ID,"run_id":RUN_ID,"batch_id":BATCH_ID,
        "tool":TOOL,"tool_version":TOOL_VERSION,
        "doc_count": emitted,
        "events_blob": f"{OCS_PREFIX}events.jsonl.gz",
        "events_sha256": sha,
        "created_at": iso_now()
    })
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
