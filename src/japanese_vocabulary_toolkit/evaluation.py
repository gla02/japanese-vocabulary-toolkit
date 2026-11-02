from __future__ import annotations

from dataclasses import asdict, dataclass
from pathlib import Path
import csv
import json

from .models import InputTerm, ResolvedVocabulary


@dataclass(frozen=True)
class EvaluationSummary:
    total: int
    resolved: int
    review: int
    unresolved: int
    with_reading: int
    with_definition: int
    exact_dictionary_match: int
    alias_dictionary_match: int
    card_ready: int
    definition_review: int
    resolution_review: int

    @property
    def auto_resolution_rate(self) -> float:
        return self.resolved / self.total if self.total else 0.0

    @property
    def review_rate(self) -> float:
        return self.review / self.total if self.total else 0.0

    @property
    def unresolved_rate(self) -> float:
        return self.unresolved / self.total if self.total else 0.0


def read_terms(path: Path) -> list[InputTerm]:
    """Read ordered vocabulary from a newline-delimited UTF-8 file.

    Empty lines and lines beginning with # are ignored. source_index is the
    stable order of study items after those non-items are removed.
    """
    items: list[InputTerm] = []
    for raw in path.read_text(encoding="utf-8-sig").splitlines():
        value = raw.strip()
        if not value or value.startswith("#"):
            continue
        # TSV may optionally supply an authoritative reading from the source
        # list. Plain one-term-per-line input remains fully supported.
        parts = [part.strip() for part in value.split("\t")]
        original = parts[0]
        reading = parts[1] if len(parts) > 1 and parts[1] else None
        items.append(InputTerm(original=original, source_index=len(items), supplied_reading=reading))
    return items


def summarize(results: list[ResolvedVocabulary]) -> EvaluationSummary:
    def match_value(item: ResolvedVocabulary) -> str:
        return item.match_method.value if hasattr(item.match_method, "value") else str(item.match_method)

    return EvaluationSummary(
        total=len(results),
        resolved=sum(x.status == "resolved" for x in results),
        review=sum(x.status == "review" for x in results),
        unresolved=sum(x.status == "unresolved" for x in results),
        with_reading=sum(bool(x.reading) for x in results),
        with_definition=sum(bool(x.display_definition) for x in results),
        exact_dictionary_match=sum(match_value(x) == "exact" for x in results),
        alias_dictionary_match=sum(match_value(x) == "alias" for x in results),
        card_ready=sum(x.card_status == "card-ready" for x in results),
        definition_review=sum(x.card_status == "definition-review" for x in results),
        resolution_review=sum(x.card_status == "resolution-review" for x in results),
    )


def write_json(path: Path, results: list[ResolvedVocabulary], summary: EvaluationSummary) -> None:
    payload = {
        "summary": {**asdict(summary),
                    "auto_resolution_rate": summary.auto_resolution_rate,
                    "review_rate": summary.review_rate,
                    "unresolved_rate": summary.unresolved_rate},
        "results": [asdict(x) for x in results],
    }
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def write_csv(path: Path, results: list[ResolvedVocabulary]) -> None:
    with path.open("w", encoding="utf-8-sig", newline="") as fh:
        writer = csv.writer(fh)
        writer.writerow([
            "source_index", "input", "status", "expression", "reading",
            "match_method", "card_status", "definition_warnings", "definition", "alternatives"
        ])
        for item in results:
            method = item.match_method.value if hasattr(item.match_method, "value") else str(item.match_method)
            writer.writerow([
                item.source_index,
                item.original_input,
                item.status,
                item.expression or "",
                item.reading or "",
                method,
                item.card_status,
                " | ".join(item.definition_warnings),
                (item.display_definition or "").replace("\n", " / "),
                " | ".join(item.alternatives),
            ])
