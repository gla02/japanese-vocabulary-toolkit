from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).parents[1] / "src"))

from japanese_vocabulary_toolkit.html import concise_definition, definition_quality_warnings, is_reference_definition


def test_extracts_senses_without_pos_or_examples():
    html = '<div><i>adv.</i> <span style="color:#666666">1.</span> <span>物事が起こる前に。前以て。</span><br/><i style="color:#666666">“example”</i></div>'
    assert concise_definition(html) == '物事が起こる前に。前以て。'


def test_preserves_bold_synonym_and_definition():
    html = '<div><i>v.</i> <span style="color:#666666">1.</span> <b>見過ごす</b> <span style="color:#666666">— 見ていながら気がつかないでいる。見落とす。</span></div>'
    assert concise_definition(html) == '見ていながら気がつかないでいる。見落とす。'


def test_detects_cross_reference_only_definition():
    assert is_reference_definition('<div><span>そなえる　参照</span></div>')
    assert is_reference_definition('<div><span>したがっての漢字表記。</span></div>')
    assert not is_reference_definition('<div><span>不要なものを取り除く。省略する。</span></div>')


def test_many_senses_alone_do_not_force_review():
    html = '<div><i>n.</i><span>一。</span><br/><span>二。</span><br/><span>三。</span></div>'
    assert definition_quality_warnings(html) == []


def test_concise_definition_strips_synonym_prefix():
    html = '<div><i>n.</i> <span style="color:#666">1.</span> <b>好機, チャンス</b> <span>— 何かをするのに丁度よいとき。</span></div>'
    assert concise_definition(html) == '何かをするのに丁度よいとき。'


def test_dependent_gogi_reference_is_flagged():
    html = '<div><i>n.</i><span>値打ち。</span><br/><span>特に、語義1において、積極的に評価しうるもの。</span></div>'
    assert 'dependent-sense-reference' in definition_quality_warnings(html)


def test_long_display_sense_is_flagged():
    long = '状況を説明するための長い文章です。' * 8
    html = f'<div><i>n.</i><span>{long}</span></div>'
    assert 'long-display-sense' in definition_quality_warnings(html)


def test_latin_etymology_parenthesis_is_removed():
    html = '<div><i>n.</i><b>要件, 前提</b><span>— あることが成り立つのに必要な事柄（ラテン語condiciōの訳語として）。</span></div>'
    assert concise_definition(html) == 'あることが成り立つのに必要な事柄。'


def test_spelling_label_is_skipped_for_real_meaning():
    html = '<div><i>v.</i><b>準備, 整備</b><span>— 【備える・具える】</span><br/><span>そのことがいつあってもいいように前もって用意する。</span><br/><span>物や状態をそろえておく。</span></div>'
    assert concise_definition(html) == 'そのことがいつあってもいいように前もって用意する。\n物や状態をそろえておく。'


def test_reference_same_as_is_detected():
    assert is_reference_definition('<div><span>「はいいろ」に同じ。</span><br/><span>「はいいろ」を参照。</span></div>')


def test_transitivity_conflict_is_conservative():
    from japanese_vocabulary_toolkit.html import transitivity_conflicts
    html = '<div><i>v.</i><i style="color:#666">(intransitive)</i><span>はいる。</span></div>'
    assert transitivity_conflicts(html, ("Godan verb", "transitive verb"))
    assert not transitivity_conflicts(html, ("Godan verb", "intransitive verb"))


def test_explicit_written_form_prefix_can_reject_homograph():
    from japanese_vocabulary_toolkit.html import expression_prefix_conflicts
    assert expression_prefix_conflicts('（吹く）風が動いて通る。', '拭く')
    assert not expression_prefix_conflicts('（拭く）布で汚れを取る。', '拭く')
    assert not expression_prefix_conflicts('（きち）活動の拠点。', '基地')


def test_dated_and_slang_senses_are_skipped():
    html = '<div><i>adv.</i><span>1.</span><i style="color:#666">(dated)</i><span>古い意味。</span><br/><span>2.</span><span>現代の意味。</span></div>'
    assert concise_definition(html) == '現代の意味。'

    html2 = '<div><i>n.</i><span>1.</span><span>普通の意味。</span><br/><span>2.</span><i style="color:#666">(Internet, abbreviation, slang)</i><span>ネット俗語。</span></div>'
    assert concise_definition(html2) == '普通の意味。'

def test_styled_examples_are_not_senses():
    html = '<div><i>n.</i><span>1.</span><span>本当の意味。</span><br/><i style="color:#666">“長い用例文”</i><br/><span>2.</span><span>第二の意味。</span></div>'
    assert concise_definition(html) == '本当の意味。\n第二の意味。'


def test_numeric_dependent_reference_is_flagged_broadly():
    html = '<div><i>n.</i><span>道具。</span><br/><span>1 ですくう量。</span></div>'
    assert 'dependent-sense-reference' in definition_quality_warnings(html)


def test_circular_definition_repeating_reading_is_flagged():
    html = '<div><i>n.</i><span>こゆび。</span></div>'
    warnings = definition_quality_warnings(
        html, preferred_expression='小指', preferred_reading='こゆび'
    )
    assert 'circular-display-definition' in warnings


def test_circular_definition_repeating_word_is_flagged():
    html = '<div><i>n.</i><span>相撲。</span></div>'
    warnings = definition_quality_warnings(
        html, preferred_expression='相撲', preferred_reading='すもう'
    )
    assert 'circular-display-definition' in warnings


def test_definition_that_mentions_headword_but_explains_it_is_not_circular():
    html = '<div><i>n.</i><span>小指に付ける指輪。</span></div>'
    warnings = definition_quality_warnings(
        html, preferred_expression='小指', preferred_reading='こゆび'
    )
    assert 'circular-display-definition' not in warnings
