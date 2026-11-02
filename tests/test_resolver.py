from functools import lru_cache
from pathlib import Path
import os
import sys
import pytest

sys.path.insert(0, str(Path(__file__).parents[1] / "src"))

from japanese_vocabulary_toolkit.jmdict import JmdictLexicon
from japanese_vocabulary_toolkit.resolver import VocabularyResolver
from japanese_vocabulary_toolkit.stardict import StarDictDictionary

BASE = Path(os.environ.get("KOTOBA_ANKI_TEST_DICT", Path(__file__).parents[1] / "source_dict" / "ja-ja" / "ja-ja"))
JMDICT = Path(os.environ.get("KOTOBA_ANKI_TEST_JMDICT", "JMdict.gz"))


@lru_cache(maxsize=1)
def _real_resolver():
    if not JMDICT.exists() or not BASE.with_suffix(".idx").exists():
        pytest.skip("real dictionary integration data not configured")
    return VocabularyResolver(StarDictDictionary(BASE), JmdictLexicon(JMDICT))


def test_real_jmdict_can_select_adjective_block_when_available():
    resolver = _real_resolver()
    result = resolver.resolve("良い")
    assert result.status == "resolved"
    assert result.reading == "よい"
    assert "すばらしい" in (result.display_definition or "")
    assert "日が沈んだ直後" not in (result.display_definition or "")


def test_kana_input_spelling_is_preserved_with_real_jmdict():
    resolver = _real_resolver()
    result = resolver.resolve("あらかじめ")
    assert result.expression == "あらかじめ"
    assert result.reading == "あらかじめ"


def test_alias_without_jmdict_reading_is_review_with_real_jmdict():
    resolver = _real_resolver()
    result = resolver.resolve("収集する")
    assert result.status == "review"
    assert result.reading is None


def test_exact_written_form_beats_homonymous_reading_entry_with_real_jmdict():
    resolver = _real_resolver()
    for term, expected in [
        ("意識", "自己または外界"),
        ("価値", "重要さ"),
    ]:
        result = resolver.resolve(term)
        assert result.status == "resolved"
        assert expected in (result.display_definition or "")


def test_reading_label_filters_historical_homonym_with_real_jmdict():
    resolver = _real_resolver()
    result = resolver.resolve("影響")
    assert "【えいきょう】" in (result.display_definition or "")
    assert "【ようごう】" not in (result.display_definition or "")


def test_alternate_jmdict_spelling_can_bridge_dictionary_convention():
    resolver = _real_resolver()
    result = resolver.resolve("徐々に")
    assert result.status == "resolved"
    assert result.expression == "徐々に"
    assert result.reading == "じょじょに"
    assert "緩やかに" in (result.display_definition or "")


def test_reference_stub_follows_reading_definition_with_real_jmdict():
    resolver = _real_resolver()
    for term, expected in [
        ("及ぼす", "作用"),
        ("備える", "用意"),
        ("防ぐ", "食い止め"),
    ]:
        result = resolver.resolve(term)
        assert result.expression == term
        assert result.status == "resolved"
        assert "参照" not in (result.display_definition or "")
        assert expected in (result.display_definition or "")


def test_definition_quality_separates_resolution_from_card_readiness():
    resolver = _real_resolver()
    assert resolver.resolve("検討").card_status == "card-ready"
    # Many source senses alone no longer force review; the checker now flags
    # concrete defects in the displayed definition instead.
    assert resolver.resolve("対応").card_status == "card-ready"
    assert resolver.resolve("状況").card_status == "definition-review"
    assert resolver.resolve("価値").card_status == "definition-review"
    assert resolver.resolve("収集する").card_status == "resolution-review"

def test_synonym_prefixes_are_removed_from_card_display():
    resolver = _real_resolver()
    result = resolver.resolve("機会")
    assert result.card_status == "card-ready"
    assert result.display_definition == "何かをするのに丁度よいとき。"

def test_unscoped_homonymous_reading_is_definition_review():
    resolver = _real_resolver()
    for term in ("溶ける", "反る", "掻く"):
        result = resolver.resolve(term)
        assert result.card_status == "definition-review"
        assert "homonymous-reading-unscoped" in result.definition_warnings
