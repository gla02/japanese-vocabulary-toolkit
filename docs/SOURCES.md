# Supported data sources

Japanese Vocabulary Toolkit keeps source data outside the Python package. This makes updates and licensing boundaries explicit.

## Japanese StarDict dictionary

The resolver expects a Japanese monolingual StarDict dictionary with `.ifo`, `.idx`, `.dict`/`.dict.dz` and optionally `.syn` files.

The project has been developed against the Japanese Wiktionary-derived dictionary published by Daniel Gregorini / Kaikki-Wiktextract. Other StarDict dictionaries may work if their HTML structure is compatible, but are not yet guaranteed providers.

Pass the common base path, for example `data/ja-ja/ja-ja`.

## JMdict

JMdict is used for lexical identity: written forms, readings, restrictions, priorities and parts of speech. JVT can also render JMdict glosses in requested languages.

Use the normal JMdict XML or XML.gz file with `--jmdict`.

Common language codes found in JMdict include `eng`, `dut`, `fre`, `ger`, `hun`, `rus`, `slv`, `spa`, and `swe`; actual coverage depends on the downloaded file.

JVT stores requested glosses as card enrichment only. Multilingual glosses are not assumed to align perfectly sense-for-sense.

## OpenJLPT

OpenJLPT is optional. It provides the easiest no-custom-list workflow and useful metadata such as stable IDs, readings, JLPT bands, POS, JMdict IDs, meanings and examples.

Place files named `n5.json`, `n4.json`, ..., `n1.json` in one directory and use `--jlpt` plus `--openjlpt-dir`.

OpenJLPT is not required for custom TXT/CSV/JSON builds.

## Frequency data

A Jiten-style `Word,Form,Rank` CSV can be attached with `--frequency`. JVT also accepts common alternative column names for word, reading and rank.

Frequency only changes ordering. Missing or conflicting ranks never alter lexical resolution.

## Licensing

JVT does not redistribute these datasets. Refer to each upstream project for current license terms before redistributing source-derived data or generated decks.
