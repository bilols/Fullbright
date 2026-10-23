"""Where kit_build finds texture families.

Built-in examples live in `fullbright.families` (its FAMILIES dict). Your own
families live in any importable package that exposes the same kind of dict:

    # mypackage/__init__.py
    FAMILIES = {"MY_WALL": "mypackage.my_wall", ...}   # family ID -> module

Point the server at it with two settings (environment or .env):

    MM_FAMILY_PATH=C:/path/to/folder/containing/mypackage   (os.pathsep-separated)
    MM_FAMILY_PACKAGES=mypackage                            (comma-separated)

Private families never need to live in this repository.
"""

from __future__ import annotations

import importlib
import sys


def families(family_path=(), family_packages=()) -> dict:
    for p in family_path:
        if p and p not in sys.path:
            sys.path.insert(0, p)
    out = dict(importlib.import_module("fullbright.families").FAMILIES)
    for pkg in family_packages:
        if not pkg:
            continue
        mod = importlib.import_module(pkg)
        out.update(getattr(mod, "FAMILIES", {}))
    return out
