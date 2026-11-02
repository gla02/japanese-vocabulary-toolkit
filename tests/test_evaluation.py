from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).parents[1] / "src"))

from japanese_vocabulary_toolkit.evaluation import read_terms, summarize
from japanese_vocabulary_toolkit.models import MatchMethod, ResolvedVocabulary


def test_read_terms_preserves_stable_input_order(tmp_path):
    path = tmp_path / "words.txt"
    path.write_text("# comment\n収集\n\n見逃す\nあらかじめ\n", encoding="utf-8")
    terms = read_terms(path)
    assert [(x.original, x.source_index) for x in terms] == [
        ("収集", 0), ("見逃す", 1), ("あらかじめ", 2)
    ]


def test_summary_counts_outcomes():
    results = [
        ResolvedVocabulary("a", status="resolved", reading="a", display_definition="x", match_method=MatchMethod.EXACT),
        ResolvedVocabulary("b", status="review", reading="b", display_definition="y", match_method=MatchMethod.AMBIGUOUS),
        ResolvedVocabulary("c", status="unresolved"),
    ]
    summary = summarize(results)
    assert summary.total == 3
    assert summary.resolved == 1
    assert summary.review == 1
    assert summary.unresolved == 1
    assert summary.with_reading == 2
    assert summary.with_definition == 2
