import json
from japanese_vocabulary_toolkit.deck_build import BuildRow, write_build_json
from japanese_vocabulary_toolkit.anki_export import stable_guid, _stable_int


def test_json_includes_all_statuses_and_unicode(tmp_path):
    rows = [BuildRow(source_index=i, source_id=f"id-{i}", level="N3", frequency_rank=None,
        input_word="橋", expression="橋", reading="はし", definition="川にかけるもの。" if i == 0 else "",
        status="resolved" if i == 0 else "review", card_status=status,
        review_reason="" if i == 0 else "ambiguous", jmdict_id="", source_meanings="",
        manual_override=False, note="日本語のメモ") for i,status in enumerate(("card-ready", "definition-review", "unresolved"))]
    file = tmp_path / "vocabulary.json"
    write_build_json(file, rows)
    data = json.loads(file.read_text(encoding="utf-8"))
    assert data["schema_version"] == "1.0"
    assert [x["card_status"] for x in data["entries"]] == ["card-ready", "definition-review", "unresolved"]
    assert data["entries"][0]["note"] == "日本語のメモ"
    assert data["entries"][0]["source_id"] == "id-0"


def test_historical_anki_id_unchanged():
    import hashlib
    assert stable_guid("id1", "はし") == hashlib.sha1("kotoba-anki:id1:はし".encode()).hexdigest()[:20]
    assert _stable_int("model", "kotoba-anki-recognition-v1") == 993190901
