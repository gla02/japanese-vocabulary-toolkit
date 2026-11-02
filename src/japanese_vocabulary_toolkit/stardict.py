from __future__ import annotations

import gzip
import struct
from collections import defaultdict
from dataclasses import dataclass
from pathlib import Path

from .models import DictionaryCandidate, MatchMethod


@dataclass(frozen=True)
class _IndexRecord:
    word: str
    offset: int
    size: int
    index: int


class StarDictDictionary:
    """Minimal StarDict reader for sametypesequence=h dictionaries.

    The current prototype eagerly decompresses the .dict.dz payload once. The
    public interface is deliberately independent of that implementation detail.
    """

    def __init__(self, base_path: str | Path):
        base = Path(base_path)
        if base.suffix in {".ifo", ".idx", ".syn"}:
            base = base.with_suffix("")
        self.base = base
        self._records: list[_IndexRecord] = []
        self._exact: dict[str, list[int]] = defaultdict(list)
        self._aliases: dict[str, list[int]] = defaultdict(list)
        self._load_index()
        self._load_synonyms()
        self._dict_bytes = self._load_dictionary_bytes()

    def _load_index(self) -> None:
        raw = self.base.with_suffix(".idx").read_bytes()
        cursor = 0
        index = 0
        while cursor < len(raw):
            end = raw.index(b"\0", cursor)
            word = raw[cursor:end].decode("utf-8")
            offset, size = struct.unpack(">II", raw[end + 1 : end + 9])
            record = _IndexRecord(word, offset, size, index)
            self._records.append(record)
            self._exact[word].append(index)
            cursor = end + 9
            index += 1

    def _load_synonyms(self) -> None:
        path = self.base.with_suffix(".syn")
        if not path.exists():
            return
        raw = path.read_bytes()
        cursor = 0
        while cursor < len(raw):
            end = raw.index(b"\0", cursor)
            alias = raw[cursor:end].decode("utf-8")
            target_index = struct.unpack(">I", raw[end + 1 : end + 5])[0]
            if target_index < len(self._records):
                self._aliases[alias].append(target_index)
            cursor = end + 5

    def _load_dictionary_bytes(self) -> bytes:
        dz = self.base.with_suffix(".dict.dz")
        plain = self.base.with_suffix(".dict")
        if dz.exists():
            with gzip.open(dz, "rb") as fh:
                return fh.read()
        return plain.read_bytes()

    def _candidate(self, query: str, record_index: int, method: MatchMethod) -> DictionaryCandidate:
        record = self._records[record_index]
        start = record.offset
        payload = self._dict_bytes[start : start + record.size].decode("utf-8")
        return DictionaryCandidate(
            query=query,
            headword=record.word,
            definition_html=payload,
            match_method=method,
            source_index=record.index,
        )

    def lookup(self, term: str) -> list[DictionaryCandidate]:
        """Return exact entries first, then unique alias/synonym targets."""
        results: list[DictionaryCandidate] = []
        seen: set[int] = set()
        for idx in self._exact.get(term, ()):
            seen.add(idx)
            results.append(self._candidate(term, idx, MatchMethod.EXACT))
        for idx in self._aliases.get(term, ()):
            if idx not in seen:
                seen.add(idx)
                results.append(self._candidate(term, idx, MatchMethod.ALIAS))
        return results

    def exact(self, term: str) -> list[DictionaryCandidate]:
        return [self._candidate(term, i, MatchMethod.EXACT) for i in self._exact.get(term, ())]

    @property
    def entry_count(self) -> int:
        return len(self._records)

    @property
    def alias_count(self) -> int:
        return sum(len(v) for v in self._aliases.values())
