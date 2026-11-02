# Architecture

`kotoba-anki` is deliberately split into three concerns: lexical resolution,
deck-build policy, and export.

## 1. Lexical resolution

`stardict.py`, `jmdict.py`, `resolver.py`, and `html.py` resolve one input term
against a Japanese monolingual dictionary with JMdict as independent lexical
evidence.

The resolver tries to establish:

- which written form is being requested,
- which reading belongs to it,
- whether the dictionary record is sufficiently scoped to that lexical item,
- whether the extracted Japanese definition is suitable for a compact card.

It returns structured evidence and separate `status` / `card_status` values.
This separation is important: a dictionary record can be structurally resolved
while its display definition is still questionable.

## 2. Deck-build policy

`deck_build.py` handles source metadata and presentation policy rather than
lexical reasoning.

It:

- reads OpenJLPT JSON/CSV,
- attaches optional frequency ranks,
- orders entries by JLPT band and frequency,
- applies explicit editorial overrides,
- separates card-ready, review, and unresolved rows,
- writes reproducible CSV/build metadata.

Frequency is ordering metadata only. It is never used as evidence that a sense
or reading is correct.

## 3. Export

`anki_export.py` turns card-ready build rows into a minimal recognition model.
Metadata remains in hidden note fields while the card displays only expression,
reading, and Japanese definition.

Anki note GUIDs are stable across definition-only editorial changes, allowing a
regenerated package to update existing notes. Deck IDs are stable per deck
name.

## Why overrides are first-class

Some dictionary ambiguity is not safely solvable from deterministic source
fusion alone. Kana homographs and dictionary records that merge spelling-
specific senses are common examples.

The project therefore treats a small explicit override file as a feature, not a
failure mode. The deterministic resolver should be conservative; editorial
judgment should be observable and reusable rather than encoded as increasingly
opaque heuristics.

## Non-goals

The current architecture does not attempt to:

- use an LLM as a runtime dependency,
- infer missing facts from frequency,
- generate example sentences or audio,
- become a full dictionary application,
- guarantee that a community JLPT list represents official exam scope.
