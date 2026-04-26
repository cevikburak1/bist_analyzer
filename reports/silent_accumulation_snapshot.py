from __future__ import annotations

import json
import os
from datetime import datetime
from pathlib import Path
from typing import Any

from analysis.silent_accumulation import SilentAccumulationResult
from config import WEB_OUTPUT_DIR

SILENT_DIR = WEB_OUTPUT_DIR / "silent_accumulation"
SILENT_REPORT_PATH = SILENT_DIR / "latest.json"


def _normalize(value: Any) -> Any:
    if isinstance(value, dict):
        return {str(k): _normalize(v) for k, v in value.items()}
    if isinstance(value, list):
        return [_normalize(v) for v in value]
    return value


def _atomic_write(path: Path, data: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_suffix(f"{path.suffix}.tmp")
    temp.write_text(json.dumps(_normalize(data), ensure_ascii=False, indent=2), encoding="utf-8")
    os.replace(temp, path)


def save_silent_accumulation_snapshot(
    results: list[SilentAccumulationResult],
    *,
    requested_symbols: int,
    groups: dict[int, list[str]],
) -> Path:
    generated_at = datetime.now().isoformat()
    rows = [result.as_dict() for result in sorted(results, key=lambda item: (item.score, -item.bottom_distance_pct), reverse=True)]
    payload = {
        "generated_at": generated_at,
        "summary": {
            "requested_symbols": requested_symbols,
            "successful_symbols": len(results),
            "flawless": sum(1 for result in results if result.score >= 3),
            "strong": sum(1 for result in results if result.score >= 2),
            "watch": sum(1 for result in results if result.score >= 1),
            "groups": {str(group): symbols for group, symbols in groups.items()},
        },
        "items": rows,
    }
    _atomic_write(SILENT_REPORT_PATH, payload)
    return SILENT_REPORT_PATH
