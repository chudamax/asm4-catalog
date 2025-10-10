import argparse, importlib, sys
from .base import BaseAdapter

def load_adapter(spec: str) -> BaseAdapter:
    if ":" not in spec:
        raise SystemExit("adapter spec must be 'module:Class'")
    mod_name, cls_name = spec.split(":", 1)
    mod = importlib.import_module(mod_name)
    cls = getattr(mod, cls_name)
    inst = cls()
    if not isinstance(inst, BaseAdapter):
        raise SystemExit(f"{cls_name} is not a BaseAdapter")
    return inst

def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--adapter", required=True, help="module:Class")
    args = ap.parse_args(argv)
    sys.exit(load_adapter(args.adapter).run())

if __name__ == "__main__":
    main()
