from __future__ import annotations

from pathlib import Path
from typing import Any
import csv
import json

from .deck_build import SourceItem, _normalise_meanings, _normalise_pos


def _first(row: dict[str, Any], *names: str) -> Any:
    lowered = {str(k).strip().lower(): v for k, v in row.items()}
    for name in names:
        if name in lowered and lowered[name] not in (None, ""):
            return lowered[name]
    return None


def _normalise_tags(value: Any) -> tuple[str, ...]:
    if value is None:
        return ()
    if isinstance(value, list):
        return tuple(str(x).strip() for x in value if str(x).strip())
    text = str(value).strip()
    if not text:
        return ()
    return tuple(x.strip() for x in text.replace("|", ";").split(";") if x.strip())


def _row_to_item(row: dict[str, Any], index: int, *, source_prefix: str) -> SourceItem | None:
    word = str(_first(row, "word", "expression", "term", "vocabulary") or "").strip()
    if not word:
        return None
    reading = str(_first(row, "reading", "kana", "pronunciation") or "").strip() or None
    level = str(_first(row, "level", "jlpt") or "").strip().upper() or None
    source_id = str(_first(row, "id", "source_id") or "").strip()
    if not source_id:
        source_id = f"{source_prefix}:{word}:{reading or ''}"
    jmdict_id = str(_first(row, "jmdict_id", "jmdict", "ent_seq") or "").strip() or None
    meanings = _normalise_meanings(_first(row, "meanings", "meaning", "gloss", "translation", "translations"))
    pos = _normalise_pos(_first(row, "pos", "part_of_speech", "parts_of_speech"))
    tags = _normalise_tags(_first(row, "tags", "tag"))
    note = str(_first(row, "note", "notes") or "").strip() or None
    return SourceItem(
        source_index=index,
        source_id=source_id,
        word=word,
        reading=reading,
        level=level,
        jmdict_id=jmdict_id,
        meanings=meanings,
        pos=pos,
        tags=tags,
        note=note,
    )


def read_plain_text(path: Path) -> list[SourceItem]:
    """Read UTF-8 text input.

    Each non-empty, non-comment line may be either a bare expression or a
    tab-separated ``expression<TAB>reading<TAB>meaning`` row. The latter is a
    compact escape hatch for users who do not want to create CSV.
    """
    items: list[SourceItem] = []
    for line in path.read_text(encoding="utf-8-sig").splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        parts = [x.strip() for x in line.split("\t")]
        row: dict[str, Any] = {"word": parts[0]}
        if len(parts) > 1 and parts[1]:
            row["reading"] = parts[1]
        if len(parts) > 2 and parts[2]:
            row["meaning"] = parts[2]
        item = _row_to_item(row, len(items), source_prefix="text")
        if item:
            items.append(item)
    return items


def read_generic_csv(path: Path) -> list[SourceItem]:
    with path.open("r", encoding="utf-8-sig", newline="") as fh:
        rows = list(csv.DictReader(fh))
    items: list[SourceItem] = []
    for row in rows:
        item = _row_to_item(row, len(items), source_prefix="csv")
        if item:
            items.append(item)
    return items


def read_generic_json(path: Path) -> list[SourceItem]:
    raw = json.loads(path.read_text(encoding="utf-8-sig"))
    if isinstance(raw, dict):
        raw = raw.get("items", raw.get("vocabulary", raw.get("words")))
    if not isinstance(raw, list):
        raise ValueError(f"Expected a JSON list (or an object containing items/vocabulary/words) in {path}")
    items: list[SourceItem] = []
    for row in raw:
        if isinstance(row, str):
            row = {"word": row}
        if not isinstance(row, dict):
            continue
        item = _row_to_item(row, len(items), source_prefix="json")
        if item:
            items.append(item)
    return items


def read_vocabulary(path: Path, *, source_type: str = "auto", levels: set[str] | None = None) -> list[SourceItem]:
    if path.is_dir():
        raise ValueError(f"Vocabulary input must be a file, not a directory: {path}")
    if not path.exists():
        raise FileNotFoundError(f"Vocabulary input not found: {path}")

    source_type = source_type.lower()
    if source_type == "openjlpt":
        from .deck_build import read_openjlpt
        return read_openjlpt(path, levels=levels)

    suffix = path.suffix.lower()
    if source_type == "auto":
        source_type = {".txt": "text", ".csv": "csv", ".json": "json"}.get(suffix, "")
        if not source_type:
            raise ValueError(f"Cannot infer input type from {path}; use --input-type")

    if source_type in {"text", "txt"}:
        items = read_plain_text(path)
    elif source_type == "csv":
        items = read_generic_csv(path)
    elif source_type == "json":
        items = read_generic_json(path)
    else:
        raise ValueError(f"Unsupported input type: {source_type}")

    if levels:
        items = [x for x in items if x.level in levels]
    return [SourceItem(**{**x.__dict__, "source_index": i}) for i, x in enumerate(items)]
