# Changelog

## 0.1.0 — initial release

- Renamed public project to Japanese Vocabulary Toolkit (`jvt`) and Python package to `japanese_vocabulary_toolkit`.
- Retained the original `vcg` and `kotoba-anki` CLI aliases and historical Anki GUID/deck/model identity logic.
- Added optional `notes` card field, appended after all earlier Anki model fields.
- Added `vocabulary.json` versioned structured export containing accepted, review and unresolved entries.
- Conservative StarDict/JMdict resolution, editorial overrides, multilingual JMdict glosses, TXT/CSV/JSON input and OpenJLPT shortcut.
- Configurable card layouts, HTML preview, CSV reports and optional Anki `.apkg` export.
- Source datasets and private editorial override corpus are not bundled.

- Documented Windows Python 3.12 installation and actual `.apkg` generation; added a disposable Anki reimport override and independent layout test instructions.

See TESTING.md for verification details and remaining application-level checks.
