from pathlib import Path
import gzip

import pytest

from japanese_vocabulary_toolkit.card_templates import resolve_layout
from japanese_vocabulary_toolkit.input_sources import read_vocabulary
from japanese_vocabulary_toolkit.jmdict import JmdictLexicon


def test_plain_text_accepts_bare_and_tab_separated_rows(tmp_path: Path):
    path = tmp_path / "words.txt"
    path.write_text("# comment\n収集\n延ばす\tのばす\textend; postpone\n", encoding="utf-8")
    rows = read_vocabulary(path)
    assert [(x.word, x.reading, x.meanings) for x in rows] == [
        ("収集", None, ()),
        ("延ばす", "のばす", ("extend", "postpone")),
    ]


def test_generic_csv_aliases_and_metadata(tmp_path: Path):
    path = tmp_path / "words.csv"
    path.write_text(
        "expression,kana,translation,tags,notes\n収集,しゅうしゅう,collection,mined;news,seen in article\n",
        encoding="utf-8",
    )
    row = read_vocabulary(path)[0]
    assert row.word == "収集"
    assert row.reading == "しゅうしゅう"
    assert row.meanings == ("collection",)
    assert row.tags == ("mined", "news")
    assert row.note == "seen in article"


def test_generic_json_can_be_string_list(tmp_path: Path):
    path = tmp_path / "words.json"
    path.write_text('["猫", "犬"]', encoding="utf-8")
    assert [x.word for x in read_vocabulary(path)] == ["猫", "犬"]


def test_card_presets_and_custom_fields():
    assert resolve_layout("immersion").back == ("reading", "definition_ja")
    assert resolve_layout("bilingual").back == ("reading", "definition_ja", "jmdict_gloss", "input_meaning")
    custom = resolve_layout("immersion", "expression,reading", "definition_ja,tags")
    assert custom.name == "custom"
    assert custom.front == ("expression", "reading")
    assert custom.back == ("definition_ja", "tags")
    with pytest.raises(ValueError, match="Unknown card fields"):
        resolve_layout("immersion", None, "banana")


def test_jmdict_multilingual_glosses_respect_language_and_sense_restriction(tmp_path: Path):
    xml = '''<JMdict><entry><ent_seq>1</ent_seq>
    <k_ele><keb>橋</keb></k_ele><k_ele><keb>箸</keb></k_ele>
    <r_ele><reb>はし</reb></r_ele>
    <sense><stagk>橋</stagk><gloss>bridge</gloss><gloss xml:lang="spa">puente</gloss></sense>
    <sense><stagk>箸</stagk><gloss>chopsticks</gloss><gloss xml:lang="spa">palillos</gloss></sense>
    </entry></JMdict>'''
    path = tmp_path / "JMdict.xml"
    path.write_text(xml, encoding="utf-8")
    lex = JmdictLexicon(path)
    assert lex.glosses("橋", "はし", ("eng", "spa")) == {"eng": ("bridge",), "spa": ("puente",)}
    assert lex.glosses("箸", "はし", ("eng", "spa")) == {"eng": ("chopsticks",), "spa": ("palillos",)}


def test_jmdict_gloss_limit_is_applied_in_build_enrichment():
    from japanese_vocabulary_toolkit.deck_build import BuildRow, attach_jmdict_glosses

    class Lex:
        def glosses(self, expression, reading, languages):
            return {"eng": ("one", "two", "three"), "spa": ("uno", "dos", "tres")}

    row = BuildRow(
        source_index=0, source_id="x", level="", frequency_rank=None,
        input_word="語", expression="語", reading="ご", definition="言葉。",
        status="resolved", card_status="card-ready", review_reason="", jmdict_id="",
        source_meanings="", manual_override=False,
    )
    enriched = attach_jmdict_glosses([row], Lex(), ("eng", "spa"), max_glosses=2)[0]
    assert enriched.jmdict_glosses == "[eng] one; two\n[spa] uno; dos"


def test_compressed_jmdict_and_target_filter(tmp_path: Path):
    xml = '''<JMdict>
      <entry><ent_seq>1</ent_seq><k_ele><keb>橋</keb></k_ele>
        <r_ele><reb>はし</reb></r_ele>
        <sense><gloss>bridge</gloss><gloss xml:lang="spa">puente</gloss></sense>
      </entry>
      <entry><ent_seq>2</ent_seq><k_ele><keb>猫</keb></k_ele>
        <r_ele><reb>ねこ</reb></r_ele><sense><gloss>cat</gloss></sense>
      </entry>
    </JMdict>'''
    path = tmp_path / 'JMdict.xml.gz'
    with gzip.open(path, 'wb') as f:
        f.write(xml.encode('utf-8'))
    lex = JmdictLexicon(path, target_forms={'橋'})
    assert lex.glosses('橋', 'はし', ('spa',)) == {'spa': ('puente',)}
    assert lex.lookup('猫') == []
    assert lex.glosses('猫', 'ねこ', ('eng',)) == {}
