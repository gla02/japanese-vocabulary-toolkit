from __future__ import annotations

import gzip
import shutil
import tempfile
from contextlib import contextmanager
try:
    from lxml import etree as ET
    _LXML = True
except ImportError:  # pragma: no cover - declared runtime dependency
    import xml.etree.ElementTree as ET
    _LXML = False
from collections import defaultdict
from dataclasses import dataclass
from pathlib import Path

from .models import LexicalCandidate

_XML_LANG = "{http://www.w3.org/XML/1998/namespace}lang"


@dataclass(frozen=True)
class _GlossSense:
    spellings: frozenset[str]
    readings: frozenset[str]
    glosses: tuple[tuple[str, str], ...]


class JmdictLexicon:
    """JMdict lexical evidence plus optional multilingual gloss retrieval.

    Gloss text is stored once per JMdict entry rather than duplicated for every
    compatible spelling/reading pair. This keeps full-JMdict startup practical.
    """

    def __init__(self, path: str | Path, target_forms: set[str] | None = None):
        self.path = Path(path)
        self.target_forms = {x for x in (target_forms or set()) if x} or None
        self._by_form: dict[str, list[LexicalCandidate]] = defaultdict(list)
        self._gloss_senses_by_entry: dict[str, tuple[_GlossSense, ...]] = {}
        self._load()

    @contextmanager
    def _parse_input(self):
        # lxml is dramatically faster when iterparse receives a filesystem
        # path instead of a Python gzip stream. Materialize compressed JMdict
        # to a temporary XML file, then remove it automatically.
        if _LXML and self.path.suffix == ".gz":
            with tempfile.NamedTemporaryFile(suffix=".xml", delete=False) as tmp:
                tmp_path = Path(tmp.name)
                with gzip.open(self.path, "rb") as src:
                    shutil.copyfileobj(src, tmp)
            try:
                yield str(tmp_path)
            finally:
                tmp_path.unlink(missing_ok=True)
            return
        if _LXML:
            yield str(self.path)
            return
        if self.path.suffix == ".gz":
            with gzip.open(self.path, "rb") as fh:
                yield fh
        else:
            with self.path.open("rb") as fh:
                yield fh

    def _load(self) -> None:
        with self._parse_input() as source:
            kwargs = {"events": ("end",)}
            if _LXML:
                kwargs.update({"tag": "entry", "load_dtd": True, "resolve_entities": True, "huge_tree": True})
            for _, elem in ET.iterparse(source, **kwargs):
                if elem.tag != "entry":
                    continue

                entry_id = elem.findtext("ent_seq") or ""
                kebs: list[tuple[str, tuple[str, ...]]] = []
                for ke in elem.findall("k_ele"):
                    keb = ke.findtext("keb")
                    if keb:
                        kebs.append((keb, tuple(x.text or "" for x in ke.findall("ke_pri"))))

                readings: list[tuple[str, tuple[str, ...], tuple[str, ...]]] = []
                for re in elem.findall("r_ele"):
                    reb = re.findtext("reb")
                    if not reb:
                        continue
                    restrictions = tuple(x.text or "" for x in re.findall("re_restr"))
                    rpri = tuple(x.text or "" for x in re.findall("re_pri"))
                    readings.append((reb, restrictions, rpri))

                if self.target_forms is not None:
                    forms = {k for k, _ in kebs} | {r for r, _, _ in readings}
                    if forms.isdisjoint(self.target_forms):
                        self._clear_entry(elem)
                        continue

                senses = elem.findall("sense")
                parts_of_speech = tuple(dict.fromkeys(
                    pos.text or "" for sense in senses for pos in sense.findall("pos") if pos.text
                ))

                gloss_senses: list[_GlossSense] = []
                for sense in senses:
                    glosses = tuple(
                        (g.attrib.get(_XML_LANG, "eng"), (g.text or "").strip())
                        for g in sense.findall("gloss") if (g.text or "").strip()
                    )
                    if glosses:
                        gloss_senses.append(_GlossSense(
                            spellings=frozenset(x.text for x in sense.findall("stagk") if x.text),
                            readings=frozenset(x.text for x in sense.findall("stagr") if x.text),
                            glosses=glosses,
                        ))
                if entry_id and gloss_senses:
                    self._gloss_senses_by_entry[entry_id] = tuple(gloss_senses)

                if kebs:
                    for keb, kpri in kebs:
                        for reb, restrictions, rpri in readings:
                            if restrictions and keb not in restrictions:
                                continue
                            cand = LexicalCandidate(
                                expression=keb, reading=reb, entry_id=entry_id,
                                reading_restrictions=restrictions, expression_priority=kpri,
                                reading_priority=rpri, parts_of_speech=parts_of_speech,
                                alternative_expressions=tuple(
                                    other_keb for other_keb, _ in kebs
                                    if other_keb != keb and (not restrictions or other_keb in restrictions)
                                ),
                            )
                            self._by_form[keb].append(cand)
                            self._by_form[reb].append(cand)
                else:
                    for reb, restrictions, rpri in readings:
                        cand = LexicalCandidate(
                            expression=reb, reading=reb, entry_id=entry_id,
                            reading_restrictions=restrictions, reading_priority=rpri,
                            parts_of_speech=parts_of_speech, alternative_expressions=(),
                        )
                        self._by_form[reb].append(cand)
                self._clear_entry(elem)

    @staticmethod
    def _clear_entry(elem) -> None:
        elem.clear()
        if _LXML:
            parent = elem.getparent()
            while parent is not None and elem.getprevious() is not None:
                del parent[0]

    def lookup(self, term: str) -> list[LexicalCandidate]:
        out: list[LexicalCandidate] = []
        seen: set[tuple[str, str, str, tuple[str, ...]]] = set()
        for candidate in self._by_form.get(term, ()):
            key = (candidate.entry_id or "", candidate.expression, candidate.reading, candidate.parts_of_speech)
            if key not in seen:
                seen.add(key)
                out.append(candidate)
        return out

    def glosses(self, expression: str, reading: str, languages: tuple[str, ...] = ("eng",)) -> dict[str, tuple[str, ...]]:
        wanted = set(languages)
        result: dict[str, list[str]] = {lang: [] for lang in languages}
        entry_ids = {
            c.entry_id for c in self._by_form.get(expression, ())
            if c.entry_id and c.expression == expression and c.reading == reading
        }
        if expression == reading:
            entry_ids.update(
                c.entry_id for c in self._by_form.get(reading, ())
                if c.entry_id and c.expression == expression and c.reading == reading
            )
        for entry_id in entry_ids:
            for sense in self._gloss_senses_by_entry.get(entry_id, ()):
                if sense.spellings and expression not in sense.spellings:
                    continue
                if sense.readings and reading not in sense.readings:
                    continue
                for lang, text in sense.glosses:
                    if lang in wanted and text not in result[lang]:
                        result[lang].append(text)
        return {lang: tuple(values) for lang, values in result.items() if values}
