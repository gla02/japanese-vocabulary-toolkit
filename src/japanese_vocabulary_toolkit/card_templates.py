from __future__ import annotations

from dataclasses import dataclass


FIELD_LABELS = {
    "expression": "Expression",
    "reading": "Reading",
    "definition_ja": "Japanese Definition",
    "input_meaning": "Input Meaning",
    "jmdict_gloss": "JMdict Gloss",
    "pos": "Part of Speech",
    "tags": "Tags",
    "notes": "Notes",
    "level": "Level",
    "frequency": "Frequency",
}


@dataclass(frozen=True)
class CardLayout:
    name: str
    front: tuple[str, ...]
    back: tuple[str, ...]


PRESETS = {
    "immersion": CardLayout("immersion", ("expression",), ("reading", "definition_ja")),
    "bilingual": CardLayout("bilingual", ("expression",), ("reading", "definition_ja", "jmdict_gloss", "input_meaning")),
    "translation": CardLayout("translation", ("expression",), ("reading", "jmdict_gloss", "input_meaning")),
    "reading": CardLayout("reading", ("expression",), ("reading",)),
    "production": CardLayout("production", ("definition_ja",), ("expression", "reading")),
}


def parse_fields(value: str | None) -> tuple[str, ...] | None:
    if value is None:
        return None
    fields = tuple(x.strip().lower() for x in value.split(",") if x.strip())
    unknown = [x for x in fields if x not in FIELD_LABELS]
    if unknown:
        raise ValueError(f"Unknown card fields: {', '.join(unknown)}")
    if not fields:
        raise ValueError("Card field list cannot be empty")
    return fields


def resolve_layout(preset: str, front_fields: str | None = None, back_fields: str | None = None) -> CardLayout:
    if preset not in PRESETS:
        raise ValueError(f"Unknown card preset {preset!r}; choose from {', '.join(sorted(PRESETS))}")
    base = PRESETS[preset]
    front = parse_fields(front_fields) or base.front
    back = parse_fields(back_fields) or base.back
    return CardLayout(preset if not (front_fields or back_fields) else "custom", front, back)
