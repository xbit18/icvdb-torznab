"""Conservative SUB ITA marker detection for optional Torznab language metadata.

Markers alone do not prove the audio is English. This opt-in workaround exists
because some downstream clients infer Italian audio from subtitle labels.
"""

import re

_ITALIAN = r"(?:ITA|ITALIAN|ITALIANO)"
_SUBTITLE = r"(?:SUB|SUBS|SUBBED|SUBTITLE|SUBTITLES|SOTTOTITOLI)"
_SUBTITLE_MARKER = re.compile(
    rf"(?<![A-Z0-9])(?:{_SUBTITLE}[\s._-]*{_ITALIAN}|{_ITALIAN}[\s._-]*{_SUBTITLE})(?![A-Z0-9])",
    re.IGNORECASE,
)
_TOKEN = re.compile(r"[A-Z0-9]+")
_ITALIAN_TOKENS = {"ITA", "ITALIAN", "ITALIANO"}
_AMBIGUOUS_AUDIO_TOKENS = {"MULTI", "DUAL"}


def should_force_english(title: str) -> bool:
    """Opt-in workaround for explicit Italian-subtitle markers only.

    Skip releases containing an independent Italian-audio marker or an
    ambiguous multiaudio marker, to avoid overwriting probable Italian audio.
    """
    if not isinstance(title, str):
        return False
    matches = list(_SUBTITLE_MARKER.finditer(title))
    if not matches:
        return False
    remainder = _SUBTITLE_MARKER.sub(" ", title)
    tokens = set(_TOKEN.findall(remainder.upper()))
    return not tokens.intersection(_ITALIAN_TOKENS | _AMBIGUOUS_AUDIO_TOKENS)
