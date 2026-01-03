# Masscan Adapter

This adapter demonstrates the new runtime SDK layering using the Masscan CLI as a proof of concept.

## Layout

- `masscan_adapter.py` contains the runnable adapter built on top of the runtime SDK.
- `fixtures/` includes sample inputs and manifests for local execution.
- `tests/` hosts smoke tests verifying the adapter contract.
- `Dockerfile` builds a runnable container based on the shared runtime image.

## Local smoke test

```
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt  # ensures pytest + build dependencies
export INPUTS_URL="file://$(pwd)/fixtures/inputs.txt"
export RESOURCES_MANIFEST_URL="file://$(pwd)/fixtures/inputs.manifest.json"
export OUTPUT_URL="file://$(pwd)/events.jsonl.gz"
asm-adapter --adapter masscan_adapter:MasscanAdapter
```

Where `fixtures/inputs.txt` contains newline separated targets and `fixtures/inputs.manifest.json` holds the parameters.
