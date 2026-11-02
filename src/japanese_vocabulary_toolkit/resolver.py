from __future__ import annotations

from collections.abc import Iterable

from .html import concise_definition, definition_quality_warnings, is_reference_definition, transitivity_conflicts, expression_prefix_conflicts, has_explicit_expression_label
from .models import InputTerm, MatchMethod, ResolvedVocabulary, ResolutionEvidence


_PRIORITY_WEIGHTS = {"ichi1": 4, "news1": 3, "spec1": 3, "gai1": 2}


def _priority_score(candidate) -> int:
    score = 0
    for marker in (*candidate.expression_priority, *candidate.reading_priority):
        score += _PRIORITY_WEIGHTS.get(marker, 0)
        if marker.startswith("nf"):
            try:
                score += max(0, 3 - (int(marker[2:]) // 10))
            except ValueError:
                pass
    return score


def _stardict_pos(parts_of_speech: tuple[str, ...]) -> str | None:
    lower = [p.lower() for p in parts_of_speech]
    if any("adjective" in p for p in lower):
        return "adj."
    if any("adverb" in p for p in lower):
        return "adv."
    # JMdict commonly represents suru words with noun + verb properties.
    # For a bare lexical item such as 意識 or 対応, the noun block is the
    # better default card definition; ordinary verbs have no noun POS and
    # still fall through to v.
    if any("noun" in p for p in lower):
        return "n."
    if any("verb" in p for p in lower):
        return "v."
    if any("interjection" in p for p in lower):
        return "interj."
    if any("particle" in p for p in lower):
        return "part."
    if any("suffix" in p for p in lower):
        return "suf."
    if any("prefix" in p for p in lower):
        return "pref."
    return None


class VocabularyResolver:
    def __init__(self, dictionary, lexicon=None):
        self.dictionary = dictionary
        self.lexicon = lexicon

    def resolve(self, term: str | InputTerm) -> ResolvedVocabulary:
        inp = term if isinstance(term, InputTerm) else InputTerm(original=term)
        lexical = self.lexicon.lookup(inp.original) if self.lexicon else []
        ranked_lexical = sorted(lexical, key=_priority_score, reverse=True)
        same_expression = [c for c in ranked_lexical if c.expression == inp.original]
        compatible = same_expression or ranked_lexical
        if inp.supplied_reading:
            reading_compatible = [c for c in compatible if c.reading == inp.supplied_reading]
            if reading_compatible:
                compatible = reading_compatible
        best_lexical = compatible[0] if compatible else None

        # Evidence ordering matters. A dictionary record exactly matching the
        # user's written form is stronger than a homonymous kana headword that
        # merely shares the JMdict reading (e.g. 意識/いしき, 価値/かち).
        original_exact = self.dictionary.exact(inp.original)
        matches: list = []
        if original_exact:
            # Exact written-form matches normally outrank kana homonyms. If the
            # exact record is only a cross-reference stub, however, follow the
            # preferred JMdict reading to the actual definition while keeping
            # the user's expression for display.
            usable_exact = [item for item in original_exact if not is_reference_definition(item.definition_html)]
            if usable_exact:
                matches = [(inp.original, "original-exact", item) for item in usable_exact]
            elif best_lexical:
                reading_exact = self.dictionary.exact(best_lexical.reading)
                if reading_exact:
                    matches = [(best_lexical.reading, "jmdict-reading-reference", item) for item in reading_exact]
            if not matches:
                matches = [(inp.original, "original-exact-reference", item) for item in original_exact]
        else:
            lookup_terms: list[tuple[str, str]] = []
            for cand in compatible:
                # Prefer an exact kana reading when the dictionary's canonical
                # record is kana-only (common for verbs such as 食べる→たべる).
                if cand.reading not in [x[0] for x in lookup_terms]:
                    lookup_terms.append((cand.reading, "jmdict-reading"))
                # Alternate JMdict spellings can bridge source conventions,
                # e.g. 徐々に in input vs 徐徐に in the monolingual dictionary.
                for alt in cand.alternative_expressions:
                    if alt not in [x[0] for x in lookup_terms]:
                        lookup_terms.append((alt, "jmdict-alternate"))
                if cand.expression not in [x[0] for x in lookup_terms]:
                    lookup_terms.append((cand.expression, "jmdict-expression"))

            for lookup_term, origin in lookup_terms:
                found_exact = self.dictionary.exact(lookup_term)
                if found_exact:
                    matches.extend((lookup_term, origin, item) for item in found_exact)
                    break

            if not matches:
                found = self.dictionary.lookup(inp.original)
                matches.extend((inp.original, "original-alias", item) for item in found)

        if not matches:
            return ResolvedVocabulary(
                original_input=inp.original,
                source_index=inp.source_index,
                reading=inp.supplied_reading,
                evidence=[ResolutionEvidence("unresolved", "resolver", "No dictionary match")],
                card_status="unresolved",
            )

        pool = matches
        distinct_records = list(dict.fromkeys(m[2].source_index for m in pool))
        selected = pool[0][2]

        expression = inp.original
        reading = inp.supplied_reading
        if best_lexical:
            if same_expression:
                expression = inp.original
            elif inp.original == best_lexical.reading:
                expression = inp.original
            else:
                expression = best_lexical.expression
            reading = reading or best_lexical.reading

        status = "resolved" if len(distinct_records) == 1 and (reading is not None or self.lexicon is None) else "review"

        preferred_pos = _stardict_pos(best_lexical.parts_of_speech) if best_lexical else None
        display_definition = concise_definition(
            selected.definition_html,
            max_senses=2,
            preferred_pos=preferred_pos,
            preferred_reading=reading,
            preferred_expression=expression,
        )
        if not display_definition:
            display_definition = concise_definition(
                selected.definition_html,
                max_senses=2,
                preferred_reading=reading,
                preferred_expression=expression,
            )

        # A reading bridge is not enough when the kana entry contains only
        # different written-form homographs. Do not silently emit a wrong card.
        if matches and matches[0][1] == "jmdict-reading-reference":
            if not display_definition:
                status = "review"
            elif best_lexical and transitivity_conflicts(selected.definition_html, best_lexical.parts_of_speech):
                status = "review"
            elif expression_prefix_conflicts(display_definition, expression):
                status = "review"

        definition_warnings = definition_quality_warnings(
            selected.definition_html,
            preferred_pos=preferred_pos,
            preferred_reading=reading,
            preferred_expression=expression,
        )
        # A kana dictionary record can merge genuinely different JMdict lexemes
        # that merely share a reading (e.g. 溶ける/解ける, 反る/剃る).
        # When the record itself does not label the requested spelling, we
        # cannot prove that the selected first senses belong to this word.
        if (
            status == "resolved"
            and matches
            and matches[0][1].startswith("jmdict-reading")
            and self.lexicon
            and reading
            and not has_explicit_expression_label(selected.definition_html, expression)
        ):
            same_pos_ids = {
                c.entry_id
                for c in self.lexicon.lookup(reading)
                if c.entry_id and _stardict_pos(c.parts_of_speech) == preferred_pos
            }
            if len(same_pos_ids) > 1:
                definition_warnings.append("homonymous-reading-unscoped")
        if status != "resolved":
            card_status = "resolution-review"
        elif definition_warnings:
            card_status = "definition-review"
        else:
            card_status = "card-ready"

        evidence = [
            ResolutionEvidence(selected.match_method.value, "ja-ja StarDict", f"{inp.original} → {selected.headword}")
        ]
        if matches[0][1].startswith("jmdict-"):
            evidence.append(ResolutionEvidence("dictionary-bridge", "JMdict", f"lookup via {matches[0][0]}"))
        if best_lexical:
            evidence.append(
                ResolutionEvidence("word-reading", "JMdict", f"{best_lexical.expression} → {best_lexical.reading}")
            )
            if preferred_pos:
                evidence.append(
                    ResolutionEvidence(
                        "part-of-speech", "JMdict", f"{', '.join(best_lexical.parts_of_speech)} → {preferred_pos}"
                    )
                )

        alternatives = []
        for _, _, candidate in pool[1:]:
            label = candidate.headword
            if label not in alternatives:
                alternatives.append(label)

        return ResolvedVocabulary(
            original_input=inp.original,
            source_index=inp.source_index,
            expression=expression,
            reading=reading,
            full_definition_html=selected.definition_html,
            display_definition=display_definition,
            match_method=selected.match_method if status == "resolved" else MatchMethod.AMBIGUOUS,
            status=status,
            evidence=evidence,
            alternatives=alternatives,
            card_status=card_status,
            definition_warnings=definition_warnings,
        )

    def resolve_many(self, terms: Iterable[str | InputTerm]) -> list[ResolvedVocabulary]:
        prepared: list[InputTerm] = []
        next_index = 0
        for term in terms:
            if isinstance(term, InputTerm):
                if term.original.strip():
                    prepared.append(term)
                continue
            value = term.strip()
            if value:
                prepared.append(InputTerm(original=value, source_index=next_index))
                next_index += 1
        return [self.resolve(term) for term in prepared]
