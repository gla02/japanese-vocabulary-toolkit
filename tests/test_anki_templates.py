import sys
import types
from pathlib import Path

from japanese_vocabulary_toolkit.anki_export import write_apkg
from japanese_vocabulary_toolkit.card_templates import resolve_layout
from japanese_vocabulary_toolkit.deck_build import BuildRow


class FakeModel:
    def __init__(self, model_id, name, fields, templates, css):
        self.model_id = model_id
        self.name = name
        self.fields = fields
        self.templates = templates
        self.css = css


class FakeNote:
    def __init__(self, model, fields):
        self.model = model
        self.fields = fields


class FakeDeck:
    last = None
    def __init__(self, deck_id, name):
        self.deck_id = deck_id
        self.name = name
        self.notes = []
        FakeDeck.last = self
    def add_note(self, note):
        self.notes.append(note)


class FakePackage:
    def __init__(self, deck):
        self.deck = deck
    def write_to_file(self, path):
        Path(path).write_text("fake", encoding="utf-8")


def row():
    return BuildRow(
        source_index=0, source_id="id1", level="N3", frequency_rank=10,
        input_word="橋", expression="橋", reading="はし", definition="川などにかけ渡す構造物。",
        status="resolved", card_status="card-ready", review_reason="", jmdict_id="1",
        source_meanings="bridge", manual_override=False,
        input_meanings="bridge", jmdict_glosses="[eng] bridge\n[spa] puente",
        pos="n", tags="mined; travel", note="remember: bridge",
    )


def test_exporter_renders_bilingual_fields_and_preserves_legacy_prefix(monkeypatch, tmp_path: Path):
    fake = types.SimpleNamespace(Model=FakeModel, Note=FakeNote, Deck=FakeDeck, Package=FakePackage)
    monkeypatch.setitem(sys.modules, "genanki", fake)
    out = tmp_path / "deck.apkg"
    write_apkg(out, [row()], "Test", layout=resolve_layout("bilingual"))
    assert out.exists()
    note = FakeDeck.last.notes[0]
    # First seven fields preserve the original model layout for upgrade compatibility.
    assert note.fields[:7] == ["橋", "はし", "川などにかけ渡す構造物。", "id1", "N3", "10", "0"]
    assert note.fields[7] == "bridge"
    assert "[spa] puente" in note.fields[8]
    qfmt = note.model.templates[0]["qfmt"]
    afmt = note.model.templates[0]["afmt"]
    assert "{{Expression}}" in qfmt
    assert "{{Definition}}" in afmt
    assert "{{JmdictGloss}}" in afmt
    assert "{{InputMeaning}}" in afmt


def test_notes_field_keeps_previous_anki_prefix(monkeypatch, tmp_path: Path):
    fake = types.SimpleNamespace(Model=FakeModel, Note=FakeNote, Deck=FakeDeck, Package=FakePackage)
    monkeypatch.setitem(sys.modules, "genanki", fake)
    write_apkg(tmp_path / "notes.apkg", [row()], "Test", layout=resolve_layout("immersion", back_fields="reading,notes"))
    note = FakeDeck.last.notes[0]
    assert note.fields[:7] == ["橋", "はし", "川などにかけ渡す構造物。", "id1", "N3", "10", "0"]
    assert note.fields[-1] == "remember: bridge"
    assert "{{Notes}}" in note.model.templates[0]["afmt"]
