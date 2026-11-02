from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).parents[1] / "src"))

from japanese_vocabulary_toolkit.jmdict import JmdictLexicon


def test_restrictions_priorities_and_pos(tmp_path):
    xml = '''<?xml version="1.0" encoding="UTF-8"?>
<JMdict>
<entry><ent_seq>1</ent_seq>
<k_ele><keb>行く</keb><ke_pri>ichi1</ke_pri></k_ele>
<r_ele><reb>いく</reb><re_pri>ichi1</re_pri></r_ele>
<r_ele><reb>ゆく</reb></r_ele>
<sense><pos>Godan verb - Iku/Yuku special class</pos><gloss>to go</gloss></sense>
</entry>
<entry><ent_seq>2</ent_seq>
<k_ele><keb>今日</keb></k_ele><k_ele><keb>今朝</keb></k_ele>
<r_ele><reb>けさ</reb><re_restr>今朝</re_restr></r_ele>
<sense><pos>noun (common) (futsuumeishi)</pos><gloss>this morning</gloss></sense>
</entry>
</JMdict>'''
    path = tmp_path / "JMdict.xml"
    path.write_text(xml, encoding="utf-8")
    d = JmdictLexicon(path)
    readings = {(x.expression, x.reading) for x in d.lookup("行く")}
    assert ("行く", "いく") in readings
    assert ("行く", "ゆく") in readings
    assert d.lookup("今日") == []
    assert [(x.expression, x.reading) for x in d.lookup("今朝")] == [("今朝", "けさ")]
    assert "verb" in d.lookup("行く")[0].parts_of_speech[0].lower()
