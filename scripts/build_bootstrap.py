#!/usr/bin/env python
"""Regenerate the embedded RUNBOOKS block in functions/_bootstrap/code.py from
files/runbooks/*.md.

Runbooks are stored in the `runbooks` TABLE (the hosted file API rejects writes
from this CLI/runtime), and the _bootstrap function carries them as base64 so it
can seed the table from inside the pod. Run this after editing any runbook:

    python scripts/build_bootstrap.py
"""
import base64
import glob
import json
import os
import re

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CODE = os.path.join(ROOT, "functions", "_bootstrap", "code.py")


def main():
    rb = {}
    for p in sorted(glob.glob(os.path.join(ROOT, "files", "runbooks", "*.md"))):
        with open(p, "rb") as f:
            rb[os.path.basename(p)] = base64.b64encode(f.read()).decode()

    items = ",\n".join(f"    {json.dumps(k)}: {json.dumps(v)}" for k, v in rb.items())
    block = "RUNBOOKS = {\n" + items + "\n}"

    src = open(CODE, encoding="utf-8").read()
    src = re.sub(r"RUNBOOKS = \{.*?\n\}", block, src, count=1, flags=re.S)
    open(CODE, "w", encoding="utf-8").write(src)
    print(f"Embedded {len(rb)} runbooks into {CODE}: {list(rb)}")


if __name__ == "__main__":
    main()
