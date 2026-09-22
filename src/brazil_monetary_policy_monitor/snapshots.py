"""Immutable raw-provider snapshots used to audit ingestion runs."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
import hashlib
import json
from pathlib import Path
from typing import Any


@dataclass(slots=True)
class RawSnapshotRun:
    root: Path
    provider: str
    series_key: str
    run_id: int
    started_at: datetime
    chunks: list[dict[str, Any]] = field(default_factory=list)

    @property
    def directory(self) -> Path:
        day = self.started_at.date().isoformat()
        safe_series = self.series_key.replace(".", "-").replace("/", "-")
        return self.root / self.provider / day / safe_series / f"run-{self.run_id:08d}"

    def save_payload(self, *, index: int, url: str, payload: bytes) -> Path:
        self.directory.mkdir(parents=True, exist_ok=True)
        filename = f"chunk-{index:03d}.json"
        path = self.directory / filename
        if path.exists():
            raise FileExistsError(f"raw snapshot already exists: {path}")
        path.write_bytes(payload)
        self.chunks.append(
            {
                "index": index,
                "url": url,
                "file": filename,
                "bytes": len(payload),
                "sha256": hashlib.sha256(payload).hexdigest(),
            }
        )
        return path

    def write_manifest(
        self,
        *,
        status: str,
        finished_at: datetime,
        records_received: int,
        error: dict[str, Any] | None = None,
    ) -> Path:
        self.directory.mkdir(parents=True, exist_ok=True)
        manifest = {
            "schema_version": 1,
            "provider": self.provider,
            "series_key": self.series_key,
            "ingestion_run_id": self.run_id,
            "started_at": self.started_at.isoformat().replace("+00:00", "Z"),
            "finished_at": finished_at.isoformat().replace("+00:00", "Z"),
            "status": status,
            "records_received": records_received,
            "chunks": self.chunks,
            "error": error,
        }
        target = self.directory / "manifest.json"
        temporary = self.directory / ".manifest.json.tmp"
        temporary.write_text(
            json.dumps(manifest, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
        temporary.replace(target)
        return target
