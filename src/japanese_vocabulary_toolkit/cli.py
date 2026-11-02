from __future__ import annotations

import argparse
import json
from dataclasses import asdict
from pathlib import Path

from .anki_export import write_apkg, write_preview_html
from .card_templates import PRESETS, FIELD_LABELS, resolve_layout
from .evaluation import read_terms, summarize, write_csv, write_json
from .jmdict import JmdictLexicon
from .deck_build import (
    attach_frequency,
    attach_jmdict_glosses,
    build_rows,
    order_items,
    read_frequency_csv,
    read_overrides,
    split_rows,
    summarize_build_rows,
    write_build_csv,
    write_build_json,
)
from .input_sources import read_vocabulary
from .resolver import VocabularyResolver
from .stardict import StarDictDictionary

_LEVEL_ORDER = {"N5": 0, "N4": 1, "N3": 2, "N2": 3, "N1": 4}


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="jvt",
        description="Japanese Vocabulary Toolkit — conservative Japanese vocabulary to reviewable Anki cards.",
    )
    parser.add_argument("--dictionary", required=True, help="Path to Japanese StarDict base, .ifo, .idx, or .syn")
    parser.add_argument("--jmdict", help="Optional path to JMdict XML or XML.gz; required for JMdict gloss output")
    sub = parser.add_subparsers(dest="command", required=True)

    lookup = sub.add_parser("lookup", help="Inspect one or more vocabulary terms")
    lookup.add_argument("terms", nargs="+")
    lookup.add_argument("--json", action="store_true")

    batch = sub.add_parser("batch", help="Resolve ordered newline-delimited vocabulary")
    batch.add_argument("input", type=Path)
    batch.add_argument("--output", type=Path)

    evaluate = sub.add_parser("evaluate", help="Resolve a vocabulary set and emit quality reports")
    evaluate.add_argument("input", type=Path)
    evaluate.add_argument("--json-output", type=Path)
    evaluate.add_argument("--csv-output", type=Path)

    build = sub.add_parser("build", help="Build validated cards from TXT/CSV/JSON or an OpenJLPT shortcut")
    build.add_argument("vocab", nargs="*", type=Path, help="Vocabulary files. TXT, CSV and JSON are supported.")
    build.add_argument(
        "--input-type", default="auto", choices=("auto", "text", "csv", "json", "openjlpt"),
        help="Input adapter. 'auto' infers generic TXT/CSV/JSON; use openjlpt for OpenJLPT metadata.",
    )
    build.add_argument(
        "--jlpt", help="Convenience mode, e.g. N5,N4 or N3,N2,N1. Reads n5.json...n1.json from --openjlpt-dir."
    )
    build.add_argument("--openjlpt-dir", type=Path, default=Path("openjlpt"), help="Directory used by --jlpt shortcut")
    build.add_argument("--levels", help="Optional comma-separated level filter for inputs that contain a level field")
    build.add_argument("--frequency", type=Path, help="Optional Jiten/other frequency CSV; affects ordering only")
    build.add_argument("--overrides", type=Path, help="Optional reusable override JSON")
    build.add_argument("--output-dir", type=Path, default=Path("output"))
    build.add_argument("--deck-name", default="Japanese Vocabulary")
    build.add_argument("--seed", type=int, default=20261027)
    build.add_argument("--shuffle-only", action="store_true", help="Ignore frequency ranks and deterministically shuffle within bands")
    build.add_argument("--no-apkg", action="store_true", help="Skip .apkg creation")
    build.add_argument("--preview-limit", type=int, default=100)
    build.add_argument(
        "--preset", choices=tuple(PRESETS), default="immersion",
        help="Card layout preset: immersion, bilingual, translation, reading, or production.",
    )
    build.add_argument(
        "--front-fields", help="Override preset front fields, comma-separated. Available: " + ",".join(FIELD_LABELS)
    )
    build.add_argument(
        "--back-fields", help="Override preset back fields, comma-separated. Available: " + ",".join(FIELD_LABELS)
    )
    build.add_argument(
        "--gloss-languages", default="",
        help="Comma-separated JMdict language codes to attach, e.g. eng,spa,fra. Requires --jmdict.",
    )
    build.add_argument(
        "--max-glosses", type=int, default=4,
        help="Maximum JMdict glosses per language on a card; 0 keeps all (default: 4).",
    )
    return parser


def _build_resolver(args, target_forms: set[str] | None = None) -> tuple[VocabularyResolver, JmdictLexicon | None]:
    base = Path(args.dictionary)
    if base.suffix in {".ifo", ".idx", ".syn"}:
        base = base.with_suffix("")
    required_index = base.with_suffix(".idx")
    if not required_index.is_file() or not (base.with_suffix(".dict").is_file() or base.with_suffix(".dict.dz").is_file()):
        raise FileNotFoundError(
            f"Japanese StarDict files not found for {base}. Supply --dictionary with the common "
            "file base (or .ifo path) of a StarDict containing .idx and .dict/.dict.dz files. "
            "See docs/SOURCES.md."
        )
    if args.jmdict and not Path(args.jmdict).is_file():
        raise FileNotFoundError(f"JMdict not found: {args.jmdict}. Supply a JMdict XML or .xml.gz file.")
    dictionary = StarDictDictionary(args.dictionary)
    lexicon = JmdictLexicon(args.jmdict, target_forms=target_forms) if args.jmdict else None
    return VocabularyResolver(dictionary, lexicon), lexicon


def _parse_levels(value: str | None) -> set[str] | None:
    if not value:
        return None
    levels = {x.strip().upper() for x in value.split(",") if x.strip()}
    invalid = sorted(x for x in levels if x not in _LEVEL_ORDER)
    if invalid:
        raise ValueError(f"Unknown JLPT levels: {', '.join(invalid)}")
    return levels


def _jlpt_paths(levels: set[str], directory: Path) -> list[Path]:
    paths: list[Path] = []
    missing: list[Path] = []
    for level in sorted(levels, key=lambda x: _LEVEL_ORDER[x]):
        candidates = [directory / f"{level.lower()}.json", directory / f"{level}.json"]
        found = next((p for p in candidates if p.exists()), None)
        if found:
            paths.append(found)
        else:
            missing.append(candidates[0])
    if missing:
        raise FileNotFoundError(
            "OpenJLPT shortcut could not find: " + ", ".join(str(x) for x in missing) +
            ". Put n5.json...n1.json in --openjlpt-dir or pass files explicitly."
        )
    return paths


def _collect_source_items(args):
    explicit_levels = _parse_levels(args.levels)
    if args.jlpt:
        jlpt_levels = _parse_levels(args.jlpt)
        assert jlpt_levels
        if args.vocab:
            raise ValueError("Use either positional vocabulary files or --jlpt, not both")
        paths = _jlpt_paths(jlpt_levels, args.openjlpt_dir)
        input_type = "openjlpt"
        levels = jlpt_levels
    else:
        if not args.vocab:
            raise ValueError("Provide one or more vocabulary files, or use --jlpt")
        paths = args.vocab
        input_type = args.input_type
        levels = explicit_levels

    source_items = []
    seen_ids: set[str] = set()
    seen_pairs: set[tuple[str, str | None]] = set()
    for path in paths:
        for item in read_vocabulary(path, source_type=input_type, levels=levels):
            pair = (item.word, item.reading)
            if item.source_id in seen_ids or pair in seen_pairs:
                continue
            seen_ids.add(item.source_id)
            seen_pairs.add(pair)
            source_items.append(item)
    return source_items, paths, levels, input_type


def _run_build(args, resolver: VocabularyResolver, lexicon: JmdictLexicon | None, collected) -> None:
    source_items, paths, levels, input_type = collected
    if args.frequency:
        source_items = attach_frequency(source_items, read_frequency_csv(args.frequency))
    source_items = order_items(source_items, seed=args.seed, frequency_first=not args.shuffle_only)

    results = resolver.resolve_many([item.to_input_term() for item in source_items])
    overrides = read_overrides(args.overrides)
    rows = build_rows(source_items, results, overrides)

    languages = tuple(x.strip() for x in args.gloss_languages.split(",") if x.strip())
    if languages and not lexicon:
        raise ValueError("--gloss-languages requires --jmdict")
    rows = attach_jmdict_glosses(rows, lexicon, languages, max_glosses=args.max_glosses)
    accepted, review, unresolved = split_rows(rows)

    layout = resolve_layout(args.preset, args.front_fields, args.back_fields)
    out = args.output_dir
    out.mkdir(parents=True, exist_ok=True)
    write_build_csv(out / "accepted.csv", accepted)
    write_build_csv(out / "review.csv", review)
    write_build_csv(out / "unresolved.csv", unresolved)
    write_build_csv(out / "all_results.csv", rows)
    write_build_json(out / "vocabulary.json", rows)
    write_preview_html(out / "preview.html", accepted, layout=layout, limit=args.preview_limit)

    manifest = {
        "generator": "Japanese Vocabulary Toolkit",
        "deck_name": args.deck_name,
        "input_type": input_type,
        "levels": sorted(levels or (), key=lambda x: _LEVEL_ORDER.get(x, 99)),
        "preset": layout.name,
        "front_fields": list(layout.front),
        "back_fields": list(layout.back),
        "jmdict_gloss_languages": list(languages),
        "max_glosses_per_language": args.max_glosses,
        "seed": args.seed,
        "frequency_source": str(args.frequency) if args.frequency else None,
        "vocab_sources": [str(x) for x in paths],
        "counts": {
            "input": len(rows),
            "accepted": len(accepted),
            "review": len(review),
            "unresolved": len(unresolved),
            "manual_overrides": sum(x.manual_override for x in rows),
            "with_frequency": sum(x.frequency_rank is not None for x in rows),
            "with_jmdict_gloss": sum(bool(x.jmdict_glosses) for x in rows),
        },
        "distributions": summarize_build_rows(rows),
    }
    (out / "build.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")

    print(f"Input:       {len(rows)}")
    print(f"Accepted:    {len(accepted)} ({len(accepted)/len(rows):.1%})" if rows else "Accepted:    0")
    print(f"Review:      {len(review)} ({len(review)/len(rows):.1%})" if rows else "Review:      0")
    print(f"Unresolved:  {len(unresolved)} ({len(unresolved)/len(rows):.1%})" if rows else "Unresolved:  0")
    print(f"Frequency:   {manifest['counts']['with_frequency']}/{len(rows)}")
    if languages:
        print(f"JMdict gloss:{manifest['counts']['with_jmdict_gloss']}/{len(rows)} ({','.join(languages)})")

    if not args.no_apkg:
        apkg = out / ("".join(c if c.isalnum() or c in "-_" else "_" for c in args.deck_name) + ".apkg")
        write_apkg(apkg, accepted, args.deck_name, layout=layout)
        print(f"Anki deck:   {apkg}")
    print(f"Preview:     {out / 'preview.html'}")
    print(f"JSON:        {out / 'vocabulary.json'}")
    print(f"Review file: {out / 'review.csv'}")


def main() -> None:
    args = _parser().parse_args()

    if args.command == "build":
        try:
            collected = _collect_source_items(args)
            source_items = collected[0]
            target_forms = {x.word for x in source_items} | {x.reading for x in source_items if x.reading}
            resolver, lexicon = _build_resolver(args, target_forms)
            _run_build(args, resolver, lexicon, collected)
        except (ValueError, FileNotFoundError) as exc:
            raise SystemExit(f"error: {exc}") from exc
        return

    if args.command == "lookup":
        resolver, _ = _build_resolver(args, set(args.terms))
        results = resolver.resolve_many(args.terms)
        if args.json:
            print(json.dumps([asdict(x) for x in results], ensure_ascii=False, indent=2))
            return
        for item in results:
            print(f"\n{item.original_input} [{item.status}]")
            print(f"  expression: {item.expression or '-'}")
            print(f"  reading:    {item.reading or '-'}")
            if item.display_definition:
                for line in item.display_definition.splitlines():
                    print(f"  {line}")
            if item.alternatives:
                print("  alternatives:", ", ".join(item.alternatives))
        return

    terms = read_terms(args.input)
    target_forms = {x.original for x in terms} | {x.supplied_reading for x in terms if x.supplied_reading}
    resolver, _ = _build_resolver(args, target_forms)
    results = resolver.resolve_many(terms)

    if args.command == "batch":
        payload = json.dumps([asdict(x) for x in results], ensure_ascii=False, indent=2)
        if args.output:
            args.output.write_text(payload, encoding="utf-8")
        else:
            print(payload)
        return

    summary = summarize(results)
    print(f"Total:       {summary.total}")
    print(f"Resolved:    {summary.resolved} ({summary.auto_resolution_rate:.1%})")
    print(f"Review:      {summary.review} ({summary.review_rate:.1%})")
    print(f"Unresolved:  {summary.unresolved} ({summary.unresolved_rate:.1%})")
    print(f"Reading:     {summary.with_reading}/{summary.total}")
    print(f"Definition:  {summary.with_definition}/{summary.total}")
    print(f"Card-ready:  {summary.card_ready}/{summary.total}")
    print(f"Def review:  {summary.definition_review}/{summary.total}")
    print(f"Res review:  {summary.resolution_review}/{summary.total}")

    if args.json_output:
        write_json(args.json_output, results, summary)
    if args.csv_output:
        write_csv(args.csv_output, results)


if __name__ == "__main__":
    main()
