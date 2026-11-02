from pathlib import Path

from japanese_vocabulary_toolkit.deck_build import Override, SourceItem, apply_override, attach_frequency, order_items, read_frequency_csv, read_openjlpt
from japanese_vocabulary_toolkit.anki_export import stable_guid
from japanese_vocabulary_toolkit.models import ResolvedVocabulary


def test_order_is_by_level_then_frequency_and_reproducible():
    items = [
        SourceItem(0, "a", "A", "a", "N3", frequency_rank=100),
        SourceItem(1, "b", "B", "b", "N4", frequency_rank=500),
        SourceItem(2, "c", "C", "c", "N4", frequency_rank=10),
        SourceItem(3, "d", "D", "d", "N3", frequency_rank=None),
    ]
    ordered = order_items(items, seed=7)
    assert [x.source_id for x in ordered] == ["c", "b", "a", "d"]
    assert [x.source_index for x in ordered] == list(range(4))
    assert order_items(items, seed=7) == ordered


def test_frequency_csv_exact_then_word_only(tmp_path: Path):
    path = tmp_path / "freq.csv"
    path.write_text("word,reading,rank\n遭う,あう,123\n合う,,99\n", encoding="utf-8")
    ranks = read_frequency_csv(path)
    items = [
        SourceItem(0, "x", "遭う", "あう", "N3"),
        SourceItem(1, "y", "合う", "あう", "N4"),
    ]
    attached = attach_frequency(items, ranks)
    assert attached[0].frequency_rank == 123
    assert attached[1].frequency_rank == 99


def test_guid_is_stable_and_identity_based():
    assert stable_guid("abc", "あう") == stable_guid("abc", "あう")
    assert stable_guid("abc", "あう") != stable_guid("abc", "こう")


def test_jiten_word_form_rank_frequency_csv(tmp_path: Path):
    path = tmp_path / "jiten.csv"
    path.write_text("Word,Form,Rank\n遭う,あう,321\nアイデア,アイデア,42\n", encoding="utf-8")
    ranks = read_frequency_csv(path)
    items = [
        SourceItem(0, "a", "遭う", "あう", "N2"),
        SourceItem(1, "b", "アイデア", "アイデア", "N2"),
    ]
    attached = attach_frequency(items, ranks)
    assert attached[0].frequency_rank == 321
    assert attached[1].frequency_rank == 42


def test_conflicting_frequency_pair_is_excluded(tmp_path: Path):
    path = tmp_path / "jiten.csv"
    path.write_text("Word,Form,Rank\n遭う,あう,321\n遭う,あう,999\n", encoding="utf-8")
    ranks = read_frequency_csv(path)
    assert ("遭う", "あう") not in ranks


def test_guid_does_not_depend_on_definition_text():
    # Note identity is deliberately source-id + reading only; editorial changes
    # to a definition must update the existing Anki note rather than duplicate it.
    before = stable_guid("openjlpt:abc123", "のばす")
    after = stable_guid("openjlpt:abc123", "のばす")
    assert before == after


def test_editorial_override_strips_bare_circular_lines_only():
    item = ResolvedVocabulary(
        original_input="空気", source_index=0, expression="空気", reading="くうき",
        display_definition="old", status="resolved", card_status="card-ready"
    )
    override = Override(
        word="空気", reading="くうき",
        definition="地球の表面を取り巻く気体。\n空気。", action="accept"
    )
    result = apply_override(item, override)
    assert result.display_definition == "地球の表面を取り巻く気体。"


def test_editorial_override_keeps_headword_inside_real_definition():
    item = ResolvedVocabulary(
        original_input="相撲", source_index=0, expression="相撲", reading="すもう",
        display_definition="old", status="resolved", card_status="card-ready"
    )
    override = Override(
        word="相撲", reading="すもう",
        definition="相撲は二人の力士が土俵上で競う競技。", action="accept"
    )
    result = apply_override(item, override)
    assert result.display_definition == "相撲は二人の力士が土俵上で競う競技。"


def test_order_places_n5_before_higher_jlpt_levels():
    items = [
        SourceItem(0, "n4", "四", "よん", "N4", frequency_rank=1),
        SourceItem(1, "n5", "五", "ご", "N5", frequency_rank=999),
        SourceItem(2, "n3", "三", "さん", "N3", frequency_rank=1),
    ]
    ordered = order_items(items, seed=1)
    assert [x.level for x in ordered] == ["N5", "N4", "N3"]


def test_openjlpt_directory_error_is_actionable(tmp_path: Path):
    import pytest
    with pytest.raises(ValueError, match="not a directory"):
        read_openjlpt(tmp_path)


def test_openjlpt_rejects_unknown_extension(tmp_path: Path):
    import pytest
    path = tmp_path / "words.txt"
    path.write_text("x", encoding="utf-8")
    with pytest.raises(ValueError, match="expected .json or .csv"):
        read_openjlpt(path)
