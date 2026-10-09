import pytest

from result_processor import ResultProcessingError, process_results


def row(title, seeders=10, provider="provider", size=100):
    return (title, size, seeders, provider, None, title + "-hash", "movie")


def test_unfiltered_preserves_input_order():
    rows = [row("second", 2), row("first", 20)]

    assert process_results(rows, "unfiltered", []) == rows


def test_italian_preferred_uses_token_markers_and_stable_scores():
    rows = [
        row("Capital.Release"),
        row("Movie.MULTI.1080p"),
        row("Movie.ITA.1080p"),
        row("Movie.ITALIANO.720p"),
        row("Movie.DUAL.1080p"),
    ]

    result = process_results(rows, "italian_preferred", [])

    assert [item[0] for item in result] == [
        "Movie.ITA.1080p",
        "Movie.ITALIANO.720p",
        "Movie.MULTI.1080p",
        "Movie.DUAL.1080p",
        "Capital.Release",
    ]


def test_italian_only_requires_an_explicit_marker():
    rows = [
        row("Movie.MULTI.1080p"),
        row("Movie.ITALIAN.1080p"),
        row("Movie.DUAL.1080p"),
        row("Movie.ITA.720p"),
        row("Capital.Release"),
    ]

    result = process_results(rows, "italian_only", [])

    assert [item[0] for item in result] == [
        "Movie.ITALIAN.1080p",
        "Movie.ITA.720p",
    ]


def test_custom_excludes_before_scoring_and_preserves_ties():
    rows = [
        row("Movie WEB", 5, "alpha"),
        row("Movie CAM", 100, "alpha"),
        row("Movie WEB", 5, "beta"),
    ]
    rules = [
        rule("title", "contains", "CAM", "exclude"),
        rule("provider", "equals", "alpha", "score", score=25),
    ]

    result = process_results(rows, "custom", rules)

    assert [item[0] for item in result] == ["Movie WEB", "Movie WEB"]
    assert [item[3] for item in result] == ["alpha", "beta"]


def test_custom_scores_change_order_with_stable_ties():
    rows = [
        row("first", provider="plain"),
        row("second", provider="fav"),
        row("third", provider="fav"),
    ]
    rules = [rule("provider", "equals", "fav", "score", score=10)]

    result = process_results(rows, "custom", rules)

    assert [item[0] for item in result] == ["second", "third", "first"]


def test_custom_minimum_seeders_nulls_and_disabled_rules():
    rows = [
        row("keep", 5, None, None),
        row("low", 2),
        row("unknown", None),
    ]
    rules = [
        rule("seeders", "lte", 4, "exclude"),
        rule("title", "contains", "keep", "exclude", enabled=False),
        rule("size", "gte", 1000, "score", score=10),
    ]

    assert process_results(rows, "custom", rules) == [rows[0], rows[2]]


def rule(field, operator, value, action, score=None, enabled=True):
    value = {
        "enabled": enabled,
        "field": field,
        "operator": operator,
        "value": value,
        "action": action,
    }
    if score is not None:
        value["score"] = score
    return value


@pytest.mark.parametrize(
    "rules",
    [
        [rule("title", "regex", ".*", "exclude")],
        [rule("unknown", "equals", "x", "exclude")],
        [rule("seeders", "contains", "1", "exclude")],
        [rule("title", "contains", "x", "drop")],
        [rule("title", "contains", "x", "score")],
        [rule("title", "contains", "x", "exclude", score=1)],
        [{"enabled": True, "field": "title"}],
    ],
)
def test_invalid_rule_shapes_are_rejected(rules):
    with pytest.raises(ResultProcessingError):
        process_results([row("Movie")], "custom", rules)


def test_italian_presets_respect_optional_subtitle_correction():
    rows = [row("Show.SUB.ITA"), row("Show.ITA"), row("Show.MULTI.SUB.ITA")]
    assert [r[0] for r in process_results(rows, "italian_only", [])] == [
        "Show.SUB.ITA",
        "Show.ITA",
        "Show.MULTI.SUB.ITA",
    ]
    assert [
        r[0] for r in process_results(rows, "italian_only", [], subtitle_language_correction=True)
    ] == ["Show.ITA", "Show.MULTI.SUB.ITA"]
    assert [
        r[0]
        for r in process_results(rows, "italian_preferred", [], subtitle_language_correction=True)
    ] == ["Show.ITA", "Show.MULTI.SUB.ITA", "Show.SUB.ITA"]
