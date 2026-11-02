from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum


class MatchMethod(str, Enum):
    EXACT = "exact"
    ALIAS = "alias"
    LEMMA = "lemma"
    AMBIGUOUS = "ambiguous"
    UNRESOLVED = "unresolved"


@dataclass(frozen=True)
class InputTerm:
    original: str
    source_index: int = 0
    supplied_reading: str | None = None
    normalized_candidates: tuple[str, ...] = ()


@dataclass(frozen=True)
class LexicalCandidate:
    expression: str
    reading: str
    entry_id: str | None = None
    reading_restrictions: tuple[str, ...] = ()
    expression_priority: tuple[str, ...] = ()
    reading_priority: tuple[str, ...] = ()
    parts_of_speech: tuple[str, ...] = ()
    alternative_expressions: tuple[str, ...] = ()


@dataclass(frozen=True)
class DictionaryCandidate:
    query: str
    headword: str
    definition_html: str
    match_method: MatchMethod
    source_index: int


@dataclass(frozen=True)
class ResolutionEvidence:
    kind: str
    source: str
    detail: str


@dataclass
class ResolvedVocabulary:
    original_input: str
    source_index: int = 0
    expression: str | None = None
    reading: str | None = None
    full_definition_html: str | None = None
    display_definition: str | None = None
    match_method: MatchMethod = MatchMethod.UNRESOLVED
    status: str = "unresolved"
    evidence: list[ResolutionEvidence] = field(default_factory=list)
    alternatives: list[str] = field(default_factory=list)
    manual_override: bool = False
    card_status: str = "unresolved"
    definition_warnings: list[str] = field(default_factory=list)
