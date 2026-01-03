# Masscan-only Adapter

This adapter demonstrates the new runtime SDK layering using the Masscan CLI as a proof of concept.

## Layout

- `adapter/` contains the runnable adapter built on top of the runtime SDK.
- `conf/` includes sample profiles for local execution.
- `tests/` hosts smoke tests verifying the adapter contract.
- `Dockerfile` builds a runnable container that installs the runtime + wrapper wheels.

## Local smoke test

```
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt  # ensures pytest + build dependencies
export INPUTS_URL="file://$(pwd)/inputs.txt"
export RESOURCES_MANIFEST_URL="file://$(pwd)/manifest.json"
export OUTPUT_URL="file://$(pwd)/events.jsonl.gz"
python -m asm_adapter_runtime.cli --adapter adapter.masscan_adapter:MasscanAdapter
```

Where `inputs.txt` contains newline separated targets and `manifest.json` resembles `conf/profile.example.yaml`.
