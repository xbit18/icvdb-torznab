import pytest

from release_language import should_force_english


@pytest.mark.parametrize(
    "title",
    [
        "Rick and Morty S09E04 [SUB ITA]",
        "Rick.and.Morty.S09E04.SUB.ITA",
        "Rick.and.Morty.S09E04.SUB-ITA",
        "Rick.and.Morty.S09E04.SUB_ITA",
        "Rick.and.Morty.S09E04.SUBITA",
        "Rick.and.Morty.S09E04.ITA.SUBBED",
        "Rick.and.Morty.S09E04.SUBS.ITALIAN",
        "Rick.and.Morty.S09E04.ITALIAN.SUBTITLES",
        "Rick.and.Morty.S09E04.sottotitoli-italiano",
        "Show.ENG.[SUB ITA]",
    ],
)
def test_explicit_subtitle_markers(title):
    assert should_force_english(title) is True


@pytest.mark.parametrize(
    "title",
    [
        "Movie.ITA.ENG.1080p",
        "Movie.ITA.SUB.ITA.1080p",
        "Movie.ITA.DUB.SUB.ITA",
        "Movie.MULTI.SUB.ITA",
        "Movie.DUAL.SUB.ITA",
        "Movie.SUB.ITA.MULTI",
        "Movie.1080p.English",
        "Movie.SUBTITLED",
        "Movie.SUBITALIANOEXTRA",
        "Movie.ITA.1080p",
        "",
    ],
)
def test_ambiguous_audio_or_unrelated_tokens(title):
    assert should_force_english(title) is False
