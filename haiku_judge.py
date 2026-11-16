"""File-based Haiku 5.5 batch protocol for Claude Desktop.

Python never calls a model. It writes small batch files; the Claude Desktop
session spawns one Agent subagent per batch with ``model: "haiku"`` (Haiku 5.5),
each subagent reads ``<kind>_NNN.input.json`` and writes ``<kind>_NNN.result.json``.
Python then reads and validates the results. Anything missing or invalid is
reported to the caller so it can fail closed (route to Needs Review).
"""

import json
from pathlib import Path

from config import HAIKU_BATCH_SIZE, HAIKU_MODEL_ID

RESULT_FORMAT = (
    'Write ONLY a JSON object to the result file: {"<item key>": <answer>, ...}. '
    "Use exactly the keys from `items`. Every choice must be one of the listed "
    "criteria keys. No prose, no code fences."
)


def batch_dir(run_dir: Path) -> Path:
    path = Path(run_dir) / "_haiku"
    path.mkdir(parents=True, exist_ok=True)
    return path


def write_batches(run_dir: Path, kind: str, instructions: str, questions: dict | None,
                  items: dict[str, dict], size: int = HAIKU_BATCH_SIZE) -> list[Path]:
    """Write ``<kind>_NNN.input.json`` batches; returns the input file paths."""
    out = batch_dir(run_dir)
    for stale in out.glob(f"{kind}_*.json"):
        stale.unlink()
    keys = list(items)
    paths = []
    for number, start in enumerate(range(0, len(keys), size), 1):
        chunk = {key: items[key] for key in keys[start:start + size]}
        path = out / f"{kind}_{number:03d}.input.json"
        payload = {
            "model": HAIKU_MODEL_ID,
            "kind": kind,
            "instructions": instructions,
            "result_format": RESULT_FORMAT,
            "result_file": path.name.replace(".input.json", ".result.json"),
            "questions": questions,
            "items": chunk,
        }
        path.write_text(json.dumps(payload, ensure_ascii=False, indent=1), encoding="utf-8")
        paths.append(path)
    return paths


def read_results(run_dir: Path, kind: str) -> dict[str, object]:
    """Merge every ``<kind>_NNN.result.json``; unreadable files are skipped."""
    merged: dict[str, object] = {}
    for path in sorted(batch_dir(run_dir).glob(f"{kind}_*.result.json")):
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            continue
        if isinstance(data, dict):
            merged.update(data)
    return merged


def pending_inputs(run_dir: Path, kind: str) -> list[Path]:
    """Input batches that have no result file yet."""
    out = batch_dir(run_dir)
    return [p for p in sorted(out.glob(f"{kind}_*.input.json"))
            if not p.with_name(p.name.replace(".input.json", ".result.json")).exists()]
