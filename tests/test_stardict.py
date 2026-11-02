from pathlib import Path
import os
import sys
import pytest

sys.path.insert(0, str(Path(__file__).parents[1] / "src"))

from japanese_vocabulary_toolkit.stardict import StarDictDictionary

BASE = Path(os.environ.get("KOTOBA_ANKI_TEST_DICT", Path(__file__).parents[1] / "source_dict" / "ja-ja" / "ja-ja"))

pytestmark = pytest.mark.skipif(not BASE.with_suffix(".idx").exists(), reason="real StarDict test data not configured")


def test_dictionary_counts():
    d = StarDictDictionary(BASE)
    assert d.entry_count == 111345
    assert d.alias_count == 523328


def test_exact_collection_entry():
    d = StarDictDictionary(BASE)
    results = d.lookup("収集")
    assert results
    assert results[0].headword == "収集"
    assert "何かを集めること" in results[0].definition_html


def test_kanji_verb_resolves_through_alias():
    d = StarDictDictionary(BASE)
    results = d.lookup("食べる")
    assert any(r.headword == "たべる" for r in results)
