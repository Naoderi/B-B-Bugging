"""Read optional local settings without executing shell commands or exposing values."""
from __future__ import annotations

import os
import re
from pathlib import Path


def load_env(path: Path | None = None) -> None:
    path = path or Path(__file__).with_name(".env")
    if not path.is_file():
        return
    settings = {}
    for number, raw in enumerate(path.read_text(encoding="utf-8-sig").splitlines(), 1):
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        if line.startswith("export "):
            line = line[7:].lstrip()
        key, separator, value = line.partition("=")
        key, value = key.strip(), value.strip()
        if not separator or not re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*", key):
            raise ValueError(f"Invalid .env setting on line {number}; use NAME=value.")
        if value.startswith(("'", '"')):
            if len(value) < 2 or value[-1] != value[0]:
                raise ValueError(f"Unclosed .env quote on line {number}.")
            value = value[1:-1]
        else:
            value = re.split(r"\s+#", value, maxsplit=1)[0].rstrip()
        settings[key] = value
    # A hosting platform or an explicit shell setting takes precedence.
    for key, value in settings.items():
        os.environ.setdefault(key, value)
