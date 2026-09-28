"""Atomic JSON publication primitives shared by static view publishers."""

from __future__ import annotations

import json
import os
from pathlib import Path
import tempfile
from typing import Any


def write_json_atomic(document: dict[str, Any], output_path: str | Path) -> Path:
    """Serialize ``document`` and atomically replace ``output_path``.

    A consumer must see either the previous complete document or the new complete
    document; it must never observe a partially written JSON file.
    """

    target = Path(output_path)
    target.parent.mkdir(parents=True, exist_ok=True)
    payload = json.dumps(
        document,
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
    ).encode("utf-8") + b"\n"

    fd, temporary_name = tempfile.mkstemp(
        prefix=f".{target.name}.", suffix=".tmp", dir=target.parent
    )
    temporary = Path(temporary_name)
    try:
        with os.fdopen(fd, "wb") as stream:
            stream.write(payload)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, target)
    except Exception:
        temporary.unlink(missing_ok=True)
        raise

    return target
