# Testing — Japanese Vocabulary Toolkit v0.1.0

## Automated tests

From the project root after installing development dependencies:

```powershell
python -m pip install -e ".[dev]"
python -m pytest -q
```

**Windows Python 3.12 (2026-10-31):** editable install succeeded, `jvt --help` ran, and the suite reported **43 passed, 13 skipped**. The skipped tests rely on external fixtures and are not failures. The user's pre-existing `~ip` pip warning did not block installation.

The self-contained suite covers lexical resolution, parsing, card templates, compressed JMdict loading, JSON export, CLI behavior, and the historical Anki identity algorithm. The test suite alone does not prove all Japanese definitions are semantically appropriate.

## Real-data verification

- In the initial hosted environment, TXT/CSV/JSON paths ran with real Japanese StarDict input; the bilingual CSV path included JMdict English/Spanish glosses. An earlier full OpenJLPT N5–N1 build with private overrides processed **7,811/7,811** card-ready entries; that result depends on the private editorial corpus, and does **not** imply equivalent automatic accuracy on arbitrary lists.
- On Windows with Python 3.12, the project processed `examples/words.csv` with StarDict and JMdict: **2 accepted, 0 review, 0 unresolved**. It wrote a real `.apkg`, an HTML preview, `vocabulary.json` and the CSV reports. The generated `.apkg` archive was inspected and contained the expected two notes and cards. The owner has imported this initial package into Anki; the update and alternate-layout tests below remain for the owner to confirm.
- The dictionary base is the **common file prefix**, e.g. `src_dict/ja-ja/ja-ja`, not just its parent directory.

## Manual Anki validation — Windows PowerShell

Run these steps in a **disposable Anki profile**, not your primary study collection. They assume the project root is your working directory and the dictionaries are at the paths shown below. Adjust the paths if yours differ.

### A. Reimport: update an existing note instead of duplicating it

The first `JVT Test` deck should already contain the two original cards from `examples/words.csv`. If not, build and import that original deck first using the first command below, *without* `--overrides`.

**Original package (only if needed):**

```powershell
jvt --dictionary ".\src_dict\ja-ja\ja-ja" --jmdict ".\JMdict.gz" build examples/words.csv --deck-name "JVT Test" --output-dir test-output
```

**Modified package:**

```powershell
jvt --dictionary ".\src_dict\ja-ja\ja-ja" --jmdict ".\JMdict.gz" build examples/words.csv --deck-name "JVT Test" --overrides examples/reimport_override.json --output-dir test-output-reimport
```

Before importing, open `test-output-reimport/preview.html`: the definition for `収集` should contain `【再インポート確認用】`; `延ばす` should be unchanged. Import `test-output-reimport/JVT_Test.apkg` into the **same Anki profile** as the original. In Anki, verify:

- The `JVT Test` deck still has **two notes / two cards**, not four.
- `収集` now shows `【再インポート確認用】ものを集めること。` (check whether Anki actually updated the existing note, not merely skipped it).
- `延ばす` is unchanged.

If Anki shows **skipped** rather than **updated** notes, do not interpret a zero-duplicate import as a complete success; inspect the import update settings and the notes' contents.

**Restore the original definition** by importing the unmodified `test-output/JVT_Test.apkg` from the original build. Confirm it restores the original text without generating duplicates. If the import settings do not update the field, this is a blocker to understanding the reimport behavior; report the Anki import summary rather than deleting or modifying existing notes manually.

### B. Non-default card layout, in a separate test deck

```powershell
jvt --dictionary ".\src_dict\ja-ja\ja-ja" --jmdict ".\JMdict.gz" build examples/words.csv --deck-name "JVT Layout Test" --front-fields expression --back-fields reading,definition_ja,notes --output-dir test-output-layout
```

Open `test-output-layout/preview.html` and import `test-output-layout/JVT_Layout_Test.apkg`. The `収集` card should show `しゅうしゅう`, the Japanese definition, and **Seen in an article** on the back. `延ばす` has no input note, so it should not show an empty notes block. This checks both selectable notes and conditional formatting. The separate deck name limits confusion with the reimport test, although the Anki note model ID is shared across decks; use a disposable profile to avoid note-type/template side effects.

### C. Final checks

- Inspect `test-output-layout/vocabulary.json` for the original expression, reading, metadata and `note` field.
- Run `git status --short` before committing. Ensure dictionary assets, output directories and any private editorial files are not staged.
- Optionally repeat the installation in a fresh virtual environment to verify full dependency resolution, rather than just reusing a Python installation with the dependencies already present.

The Anki note GUID is intentionally calculated from the historical namespace, source ID and reading. **Changing a word's source ID or reading changes its note identity.** The Anki note model has an unchanged historical model ID, with extra metadata fields appended; import template/model behavior is an application-level compatibility check, not something proven by the unit suite.
