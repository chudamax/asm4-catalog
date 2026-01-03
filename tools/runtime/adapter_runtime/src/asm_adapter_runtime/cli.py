from __future__ import annotations

import importlib
import sys

from .base import BaseAdapter


def main() -> None:
    args = sys.argv[1:]
    if "--adapter" not in args or args.index("--adapter") == len(args) - 1:
        print("usage: asm-adapter --adapter module:Class", file=sys.stderr)
        sys.exit(2)

    mod_name, cls_name = args[args.index("--adapter") + 1].split(":", 1)
    module = importlib.import_module(mod_name)
    Adapter = getattr(module, cls_name)
    if not issubclass(Adapter, BaseAdapter):
        print("Adapter must subclass BaseAdapter", file=sys.stderr)
        sys.exit(2)

    sys.exit(Adapter().run())


if __name__ == "__main__":  # pragma: no cover
    main()
