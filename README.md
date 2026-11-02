# Japanese Vocabulary Toolkit (JVT)

**Japanese vocabulary → conservative lexical validation → reviewable, configurable study cards.**

Japanese Vocabulary Toolkit is a Python CLI for Japanese learners who want to turn their own mined vocabulary (or an optional JLPT list) into study cards **without silently inventing lexical certainty**.

The default *immersion* preset deliberately contains no English:

| Front | Back |
| --- | --- |
| 延ばす | のばす<br>時間・期間・距離などを長くする。<br>予定を後にする。 |

The guiding principle is **“Do not manufacture certainty where the sources don't provide it.”** Ambiguous or incomplete candidates are separated into `review.csv` and `unresolved.csv`, rather than silently turned into cards. An independent, explicit override layer supports editorial decisions without complicating the resolver.

## Install

Requires Python **3.11+**. From the source checkout:

```bash
python -m pip install -e '.[dev]'
jvt --help
pytest -q
```

`lxml` is a required runtime dependency for reasonably fast parsing of contemporary JMdict XML; `genanki` is required to export `.apkg` files. The `vcg` and `kotoba-anki` commands remain available as compatibility aliases. The historical Anki note GUID and model IDs are unchanged.

## Provide your dictionaries

Language data is **not bundled** in this repository. Supply:

- A Japanese monolingual StarDict dictionary (e.g. Japanese Wiktionary via Kaikki), with `.ifo`, `.idx`, `.dict`/`.dict.dz` and optional `.syn` files; pass the common file base to `--dictionary`.
- JMdict XML or `.gz` via `--jmdict` for lexical validation and optional multilingual glosses. When omitted, resolution has less lexical evidence.
- Optionally a `Word,Form,Rank` frequency CSV for **ordering only**. Unknown frequency stays unknown, never “rare.”
- Optionally an editorial override JSON. See `overrides.example.json`.

See [source roles and licenses](docs/SOURCES.md) and [attribution](NOTICE.md). Check individual upstream terms before redistributing derived datasets or overrides.

## Build from your own vocabulary

```bash
jvt --dictionary data/ja-ja/ja-ja --jmdict data/JMdict.xml.gz \
  build examples/words.txt --output-dir output/txt

jvt --dictionary data/ja-ja/ja-ja --jmdict data/JMdict.xml.gz \
  build examples/words.csv --preset bilingual --gloss-languages eng,spa \
  --output-dir output/bilingual

jvt --dictionary data/ja-ja/ja-ja --jmdict data/JMdict.xml.gz \
  build examples/words.json --preset immersion --output-dir output/json
```

Supported inputs:

- **TXT**: one expression per non-comment line; optionally tab-separated `expression<TAB>reading<TAB>meaning`.
- **CSV**: headers such as `word`/`expression`, optional `reading`, `meaning`/`translation`, `tags`, `notes`, `pos`, `jlpt`, `jmdict_id`, `id`.
- **JSON**: an array of strings/objects or an object with an `items`, `words`, or `vocabulary` array.

In generic inputs, the optional supplied English meaning is **evidence or output metadata, not an automatic replacement for the Japanese definition**. Keep source IDs consistent between builds if you want Anki imports to update existing notes.

## Optional OpenJLPT shortcut

Place the source's `n5.json`…`n1.json` files in `data/openjlpt`:

```bash
jvt --dictionary data/ja-ja/ja-ja --jmdict data/JMdict.xml.gz \
  build --jlpt N3,N2,N1 --openjlpt-dir data/openjlpt \
  --frequency data/jiten_freq_global.csv --overrides my_overrides.json \
  --deck-name 'Japanese Recognition N3–N1' --output-dir output/jlpt
```

OpenJLPT is a **convenience input adapter**, not a required part of the architecture. Unlike generic JSON autodetection, the explicit `--jlpt` or `--input-type openjlpt` mode uses OpenJLPT source IDs, preserving existing note identity.

## Card layouts

| Preset | Front | Back |
| --- | --- | --- |
| `immersion` (default) | expression | reading, Japanese definition |
| `bilingual` | expression | reading, Japanese definition, JMdict gloss, supplied meaning |
| `translation` | expression | reading, JMdict gloss, supplied meaning |
| `reading` | expression | reading |
| `production` | Japanese definition | expression, reading |

Customize any preset without changing lexical resolution:

```bash
jvt --dictionary data/ja-ja/ja-ja --jmdict data/JMdict.xml.gz \
  build examples/words.csv --front-fields expression \
  --back-fields reading,definition_ja,tags --no-apkg
```

Available field names can be inspected with `jvt build --help`. `notes` is also available for custom front/back fields.

## Review and output

Every build writes `accepted.csv`, `review.csv`, `unresolved.csv`, `all_results.csv`, `preview.html`, `build.json`, and `vocabulary.json`. Unless `--no-apkg` is passed, it also writes an Anki `.apkg` containing **only accepted cards**. `vocabulary.json` contains **all entries**, including uncertain ones, in a versioned `schema_version: "1.0"` envelope. Inspect the review files; the program does not pretend a high acceptance rate is a correctness guarantee.

The Anki GUID remains based on the historical namespace plus **source ID and resolved reading**, not the definition. That allows definition corrections to update existing notes on reimport. Maintain source IDs/reading when rebuilding; changing them changes note identity.

## Architecture and testing

```text
TXT / CSV / JSON / OpenJLPT adapter
               ↓
     Normalized source entry
               ↓
  Japanese lexical resolver (JMdict + JA dictionary)
               ↓
      Explicit editorial overrides
               ↓
       Validated semantic record
               ↓
  Configurable layout / preview / Anki / review CSV + JSON
```

The JMdict loader uses `lxml` streaming parsing, stores senses/glosses once per JMdict entry, and checks spelling/reading sense restrictions at lookup time. It avoids the former explosion from copying glosses to every spelling–reading combination.

See [ARCHITECTURE.md](ARCHITECTURE.md), [TESTING.md](TESTING.md), and [CHANGELOG.md](CHANGELOG.md). The project's personal 1,262-entry editorial corpus is **not part of the public source distribution** pending provenance/licensing review.

## Scope

JVT is a Japanese-specific lexical validation tool, **not** a universal flashcard framework, an LLM-based translator, or a replacement for learning vocabulary through real reading/listening. The conservative resolution pipeline and its review files are the core feature.

Code is licensed under the [MIT License](LICENSE). Third-party source data retains its own licensing and attribution requirements.

## Verification

See [TESTING.md](TESTING.md) for automated and real-data test results, reproducible Windows/Anki compatibility checks, and their limitations. The repository does not bundle third-party dictionary data or the private editorial override corpus.
