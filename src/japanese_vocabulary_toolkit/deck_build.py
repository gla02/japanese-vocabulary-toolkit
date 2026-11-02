from __future__ import annotations

from dataclasses import dataclass, asdict
from pathlib import Path
from typing import Any
import csv
import json
import random
import unicodedata
from collections import Counter

from .models import InputTerm, ResolvedVocabulary
from .html import strip_circular_display_senses


_LEVEL_ORDER = {"N5": 0, "N4": 1, "N3": 2, "N2": 3, "N1": 4}


@dataclass(frozen=True)
class SourceItem:
    source_index: int
    source_id: str
    word: str
    reading: str | None
    level: str | None = None
    jmdict_id: str | None = None
    meanings: tuple[str, ...] = ()
    pos: tuple[str, ...] = ()
    frequency_rank: int | None = None
    tags: tuple[str, ...] = ()
    note: str | None = None

    def to_input_term(self) -> InputTerm:
        return InputTerm(
            original=self.word,
            source_index=self.source_index,
            supplied_reading=self.reading,
        )


@dataclass(frozen=True)
class Override:
    word: str
    reading: str | None = None
    definition: str | None = None
    action: str = "accept"  # accept | review | skip
    note: str | None = None


@dataclass(frozen=True)
class BuildRow:
    source_index: int
    source_id: str
    level: str
    frequency_rank: int | None
    input_word: str
    expression: str
    reading: str
    definition: str
    status: str
    card_status: str
    review_reason: str
    jmdict_id: str
    source_meanings: str
    manual_override: bool
    input_meanings: str = ""
    jmdict_glosses: str = ""
    pos: str = ""
    tags: str = ""
    note: str = ""


def _normalise_meanings(value: Any) -> tuple[str, ...]:
    if value is None:
        return ()
    if isinstance(value, list):
        return tuple(str(x).strip() for x in value if str(x).strip())
    text = str(value).strip()
    if not text:
        return ()
    # OpenJLPT CSV commonly uses semicolon-delimited glosses.
    return tuple(x.strip() for x in text.split(";") if x.strip())


def _normalise_pos(value: Any) -> tuple[str, ...]:
    if value is None:
        return ()
    if isinstance(value, list):
        return tuple(str(x).strip() for x in value if str(x).strip())
    return tuple(x.strip() for x in str(value).replace("|", ";").split(";") if x.strip())


def read_openjlpt(path: Path, *, levels: set[str] | None = None) -> list[SourceItem]:
    """Read OpenJLPT JSON or CSV while preserving stable source metadata.

    Current OpenJLPT JSON exposes stable IDs and JMdict IDs. Older/minimal CSV
    exports may omit those fields; in that case a deterministic word/reading
    identity is used as the source ID.
    """
    if path.is_dir():
        raise ValueError(
            f"Vocabulary input must be a JSON or CSV file, not a directory: {path}"
        )
    if not path.exists():
        raise FileNotFoundError(f"Vocabulary input not found: {path}")
    suffix = path.suffix.lower()
    if suffix not in {".json", ".csv"}:
        raise ValueError(f"Unsupported vocabulary format {suffix!r}; expected .json or .csv: {path}")
    records: list[dict[str, Any]]
    if suffix == ".json":
        raw = json.loads(path.read_text(encoding="utf-8-sig"))
        if not isinstance(raw, list):
            raise ValueError(f"Expected a JSON list in {path}")
        records = [x for x in raw if isinstance(x, dict)]
    else:
        with path.open("r", encoding="utf-8-sig", newline="") as fh:
            records = list(csv.DictReader(fh))

    items: list[SourceItem] = []
    for row in records:
        level = str(row.get("level") or "").upper() or None
        if levels and level not in levels:
            continue
        word = str(row.get("word") or "").strip()
        if not word:
            continue
        reading = str(row.get("reading") or "").strip() or None
        source_id = str(row.get("id") or "").strip()
        if not source_id:
            source_id = f"openjlpt:{level or 'NA'}:{word}:{reading or ''}"
        jmdict_id = str(row.get("jmdict_id") or "").strip() or None
        items.append(SourceItem(
            source_index=len(items),
            source_id=source_id,
            word=word,
            reading=reading,
            level=level,
            jmdict_id=jmdict_id,
            meanings=_normalise_meanings(row.get("meanings")),
            pos=_normalise_pos(row.get("pos")),
        ))
    return items


def _normalise_frequency_text(value: str | None) -> str | None:
    if not value:
        return None
    text = unicodedata.normalize("NFKC", value).strip()
    if not text:
        return None
    # Jiten normalises the Form/readings to hiragana. Mirror that so
    # OpenJLPT katakana readings match the same lexical form conservatively.
    chars = []
    for ch in text:
        code = ord(ch)
        if 0x30A1 <= code <= 0x30F6:
            chars.append(chr(code - 0x60))
        else:
            chars.append(ch)
    return "".join(chars)


def read_frequency_csv(path: Path) -> dict[tuple[str, str | None], int]:
    """Read a frequency CSV conservatively.

    Jiten's Global export is ``Word,Form,Rank`` where ``Form`` is the reading.
    Other common column names are accepted for convenience. Exact word+reading
    matches are preferred; a blank reading is a word-only fallback. Conflicting
    ranks for the same identity are excluded instead of guessed.
    """
    with path.open("r", encoding="utf-8-sig", newline="") as fh:
        reader = csv.DictReader(fh)
        if not reader.fieldnames:
            return {}
        fields = {name.lower().strip(): name for name in reader.fieldnames}
        word_col = next((fields[k] for k in ("word", "expression", "term", "vocabulary") if k in fields), None)
        reading_col = next((fields[k] for k in ("reading", "form", "kana", "pronunciation") if k in fields), None)
        rank_col = next((fields[k] for k in ("rank", "frequency_rank", "frequency", "freq") if k in fields), None)
        if not word_col or not rank_col:
            raise ValueError("Frequency CSV needs a word/expression column and rank/frequency column")
        rank_sets: dict[tuple[str, str | None], set[int]] = {}
        for row in reader:
            word = unicodedata.normalize("NFKC", str(row.get(word_col) or "").strip())
            if not word:
                continue
            raw_reading = str(row.get(reading_col) or "").strip() if reading_col else ""
            reading = _normalise_frequency_text(raw_reading)
            try:
                rank = int(float(str(row.get(rank_col) or "").replace(",", "")))
            except ValueError:
                continue
            if rank <= 0:
                continue
            rank_sets.setdefault((word, reading), set()).add(rank)
        return {key: next(iter(ranks)) for key, ranks in rank_sets.items() if len(ranks) == 1}


def attach_frequency(items: list[SourceItem], ranks: dict[tuple[str, str | None], int]) -> list[SourceItem]:
    result: list[SourceItem] = []
    for item in items:
        normal_word = unicodedata.normalize("NFKC", item.word)
        normal_reading = _normalise_frequency_text(item.reading)
        rank = ranks.get((normal_word, normal_reading))
        if rank is None:
            rank = ranks.get((normal_word, None))
        result.append(SourceItem(**{**asdict(item), "frequency_rank": rank}))
    return result


def order_items(items: list[SourceItem], *, seed: int = 20261027, frequency_first: bool = True) -> list[SourceItem]:
    """Order by JLPT band, then frequency; deterministic shuffle breaks ties.

    Missing frequency values come after ranked values within the same band.
    The shuffle key avoids recreating OpenJLPT's gojuon ordering for ties or
    when no frequency list is supplied.
    """
    rng = random.Random(seed)
    tie = {item.source_id: rng.random() for item in items}
    def key(item: SourceItem):
        band = _LEVEL_ORDER.get(item.level or "", 99)
        if frequency_first:
            missing = item.frequency_rank is None
            rank = item.frequency_rank if item.frequency_rank is not None else 10**12
            return (band, missing, rank, tie[item.source_id])
        return (band, tie[item.source_id])
    ordered = sorted(items, key=key)
    return [SourceItem(**{**asdict(item), "source_index": i}) for i, item in enumerate(ordered)]


def read_overrides(path: Path | None) -> dict[tuple[str, str | None], Override]:
    if path is None or not path.exists():
        return {}
    raw = json.loads(path.read_text(encoding="utf-8-sig"))
    rows = raw.get("overrides", raw) if isinstance(raw, dict) else raw
    if not isinstance(rows, list):
        raise ValueError("Override JSON must be a list or {\"overrides\": [...]} object")
    out: dict[tuple[str, str | None], Override] = {}
    for row in rows:
        if not isinstance(row, dict) or not row.get("word"):
            continue
        override = Override(
            word=str(row["word"]).strip(),
            reading=str(row.get("reading") or "").strip() or None,
            definition=str(row.get("definition") or "").strip() or None,
            action=str(row.get("action") or "accept").strip().lower(),
            note=str(row.get("note") or "").strip() or None,
        )
        out[(override.word, override.reading)] = override
    return out


def apply_override(item: ResolvedVocabulary, override: Override | None) -> ResolvedVocabulary:
    if override is None:
        return item
    if override.reading:
        item.reading = override.reading
    if override.definition:
        item.display_definition = strip_circular_display_senses(
            override.definition,
            item.expression or override.word,
            override.reading or item.reading,
        )
    item.manual_override = True
    if override.action == "skip":
        item.card_status = "unresolved"
        item.status = "unresolved"
    elif override.action == "review":
        item.card_status = "definition-review"
    else:
        if item.reading and item.display_definition:
            item.status = "resolved"
            item.card_status = "card-ready"
            item.definition_warnings = []
    return item


def build_rows(items: list[SourceItem], results: list[ResolvedVocabulary], overrides: dict[tuple[str, str | None], Override]) -> list[BuildRow]:
    source_by_index = {x.source_index: x for x in items}
    rows: list[BuildRow] = []
    for result in results:
        source = source_by_index[result.source_index]
        override = overrides.get((source.word, source.reading)) or overrides.get((source.word, None))
        result = apply_override(result, override)
        review_reason = " | ".join(result.definition_warnings)
        if result.card_status == "resolution-review" and not review_reason:
            review_reason = "resolution-review"
        elif result.card_status == "unresolved" and not review_reason:
            review_reason = "unresolved"
        rows.append(BuildRow(
            source_index=source.source_index,
            source_id=source.source_id,
            level=source.level or "",
            frequency_rank=source.frequency_rank,
            input_word=source.word,
            expression=result.expression or source.word,
            reading=result.reading or source.reading or "",
            definition=result.display_definition or "",
            status=result.status,
            card_status=result.card_status,
            review_reason=review_reason,
            jmdict_id=source.jmdict_id or "",
            source_meanings="; ".join(source.meanings),
            manual_override=result.manual_override,
            input_meanings="; ".join(source.meanings),
            pos="; ".join(source.pos),
            tags="; ".join(source.tags),
            note=source.note or "",
        ))
    return rows


def summarize_build_rows(rows: list[BuildRow]) -> dict[str, dict[str, int]]:
    """Return compact distributions useful for full-deck QA."""
    by_level = Counter(row.level or "unknown" for row in rows)
    by_card_status = Counter(row.card_status for row in rows)
    by_review_reason = Counter()
    for row in rows:
        if row.card_status in {"definition-review", "resolution-review", "unresolved"}:
            reasons = [x.strip() for x in row.review_reason.split("|") if x.strip()]
            if not reasons:
                reasons = [row.card_status]
            for reason in reasons:
                by_review_reason[reason] += 1
    return {
        "by_level": dict(sorted(by_level.items())),
        "by_card_status": dict(sorted(by_card_status.items())),
        "by_review_reason": dict(by_review_reason.most_common()),
    }


def write_build_json(path: Path, rows: list[BuildRow]) -> None:
    """Write complete vocabulary results, including review/unresolved records.

    The envelope version is independent of the Python implementation and of
    the build manifest. All records currently follow BuildRow's documented
    keys, including stable source identity and uncertainty reasons.
    """
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = {"schema_version": "1.0", "entries": [asdict(row) for row in rows]}
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def write_build_csv(path: Path, rows: list[BuildRow]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fields = [f.name for f in BuildRow.__dataclass_fields__.values()]
    with path.open("w", encoding="utf-8-sig", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=fields)
        writer.writeheader()
        for row in rows:
            writer.writerow(asdict(row))


def split_rows(rows: list[BuildRow]) -> tuple[list[BuildRow], list[BuildRow], list[BuildRow]]:
    accepted = [x for x in rows if x.card_status == "card-ready"]
    review = [x for x in rows if x.card_status in {"definition-review", "resolution-review"}]
    unresolved = [x for x in rows if x.card_status == "unresolved"]
    return accepted, review, unresolved


def attach_jmdict_glosses(rows: list[BuildRow], lexicon, languages: tuple[str, ...], *, max_glosses: int = 4) -> list[BuildRow]:
    """Attach requested JMdict glosses without changing resolver decisions."""
    if not lexicon or not languages:
        return rows
    from dataclasses import replace
    out: list[BuildRow] = []
    for row in rows:
        glosses = lexicon.glosses(row.expression, row.reading, languages)
        lines: list[str] = []
        for lang in languages:
            values = glosses.get(lang, ())
            if max_glosses > 0:
                values = values[:max_glosses]
            if values:
                lines.append(f"[{lang}] " + "; ".join(values))
        out.append(replace(row, jmdict_glosses="\n".join(lines)))
    return out
