"""Request-scoped observations; never a second query or filtering engine."""

import re
from contextvars import ContextVar
from datetime import datetime, timezone
from time import perf_counter

from release_language import should_force_english

ACTIVE_COLLECTOR = ContextVar("search_collector", default=None)
PARAMETERS = {"t", "q", "imdbid", "tmdbid", "season", "ep", "cat", "limit", "offset"}
MAX_TEXT = 512
MAX_RELEASES = 2000


def safe_text(value, limit=MAX_TEXT):
    if value is None:
        return None
    text = str(value)
    text = re.sub(r"(?:magnet:\?|[a-z][a-z0-9+.-]*://)\S*", "[redacted]", text, flags=re.I)
    text = re.sub(r"(?:/|[A-Z]:\\)[^\s]+", "[redacted]", text)
    text = re.sub(r"(?:password|apikey|api_key|token)\s*[:=]\s*\S+", "[redacted]", text, flags=re.I)
    return "".join(c for c in text if c.isprintable())[:limit]


def safe_parameters(values):
    result = {}
    changed = False
    for key in PARAMETERS:
        if key not in values:
            continue
        value = values[key]
        clean = safe_text(value) if isinstance(value, str) else value
        if clean is not None and not isinstance(clean, (str, int)):
            clean = None
        if isinstance(clean, int) and (isinstance(clean, bool) or abs(clean) > 1000000000):
            clean = None
        result[key] = clean
        changed |= clean != value
    return result, changed


def record_strategy(name):
    collector = ACTIVE_COLLECTOR.get()
    if collector is not None:
        collector.report["strategy"] = name


class SearchCollector:
    def __init__(self, *, detailed=True):
        self.detailed = detailed
        self.started = perf_counter()
        self.stage_started = self.started
        self.stage = "input"
        self.selected_ids = []
        self.report = {
            "report_version": 1,
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "original": {},
            "normalized": {},
            "strategy": None,
            "stages": {
                name: {"status": "not_run", "duration_ms": 0}
                for name in ("input", "database", "processing", "serialization")
            },
            "counts": {
                name: 0
                for name in (
                    "candidates",
                    "excluded",
                    "retained",
                    "outside_page",
                    "selected",
                    "returned",
                )
            },
            "windows": [],
            "releases": [],
            "errors": [],
            "truncated": False,
            "replayable": True,
            "limitations": [
                "Counts describe inspected SQL windows, not all database matches.",
                "Ranking is window-local; filtered pages are not backfilled.",
                "Uninspected releases may exist. Downstream acceptance is unknown.",
                "Search terms and release titles may be sensitive; review before sharing.",
            ],
        }

    def begin(self, name):
        self.stage = name
        self.stage_started = perf_counter()
        self.report["stages"][name]["status"] = "running"

    def complete(self):
        stage = self.report["stages"][self.stage]
        stage["status"] = "success"
        stage["duration_ms"] += (perf_counter() - self.stage_started) * 1000

    def fail(self):
        stage = self.report["stages"][self.stage]
        stage["status"] = "failed"
        stage["duration_ms"] += (perf_counter() - self.stage_started) * 1000
        messages = {
            "input": "Search configuration unavailable",
            "database": "Database search failed",
            "processing": "Result processing failed",
            "serialization": "Torznab serialization failed",
        }
        self.report["errors"].append(
            {"stage": self.stage, "code": f"{self.stage}_failed", "message": messages[self.stage]}
        )

    def finish(self):
        self.report["duration_ms"] = (perf_counter() - self.started) * 1000

    def inputs(self, original, normalized):
        self.report["original"], changed = safe_parameters(original)
        self.report["normalized"], changed_normalized = safe_parameters(normalized)
        self.report["truncated"] |= changed or changed_normalized
        self.report["replayable"] = not self.report["truncated"]

    def window(self, rows, limit, offset):
        self.report["windows"].append({"offset": offset, "limit": limit, "candidates": len(rows)})
        self.report["counts"]["candidates"] += len(rows)

    def safe_metadata(self, value, limit=MAX_TEXT):
        clean = safe_text(value, limit)
        self.report["truncated"] |= clean != value
        return clean

    def observer(self, window_offset, correction):
        owner = self

        class Observer:
            order = []

            def __call__(self, index, row, reason, score, score_rules):
                counts = owner.report["counts"]
                counts["excluded" if reason else "retained"] += 1
                if not owner.detailed:
                    return
                if len(owner.report["releases"]) >= MAX_RELEASES:
                    owner.report["truncated"] = True
                    return
                title = owner.safe_metadata(row[0])
                owner.report["releases"].append(
                    {
                        "id": f"{window_offset}:{index}",
                        "title": title,
                        "size": row[1],
                        "seeders": row[2],
                        "provider": owner.safe_metadata(row[3]),
                        "type": owner.safe_metadata(row[6], 32),
                        "category": 2000
                        if row[6] == "movie"
                        else 5070
                        if row[6] == "anime"
                        else 5000,
                        "language": None,
                        "subtitle_corrected_for_processing": bool(
                            correction
                            and owner.report["processing"]["preset"]
                            in {"italian_preferred", "italian_only"}
                            and should_force_english(row[0])
                        ),
                        "status": "excluded" if reason else "outside_page",
                        "reason": reason,
                        "score": score,
                        "score_rules": score_rules,
                    }
                )

        return Observer()

    def page(self, window_offset, indices):
        selected = [f"{window_offset}:{index}" for index in indices]
        self.selected_ids.extend(selected)
        self.report["counts"]["selected"] += len(indices)
        for release in self.report["releases"]:
            if release["id"] in selected:
                release["status"] = "selected"
        self.report["counts"]["outside_page"] = (
            self.report["counts"]["retained"] - self.report["counts"]["selected"]
        )

    def serialized(self, root=None):
        items = None
        if root is not None:
            items = root.findall("channel/item")
            if (
                root.tag != "rss"
                or root.find("channel") is None
                or len(items) != len(self.selected_ids)
            ):
                raise ValueError("Unexpected Torznab output")
        self.report["counts"]["returned"] = self.report["counts"]["selected"]
        releases = {release["id"]: release for release in self.report["releases"]}
        for index, candidate_id in enumerate(self.selected_ids):
            release = releases.get(candidate_id)
            if release is not None:
                release["status"] = "returned"
                if items is not None:
                    attrs = {
                        attr.get("name"): attr.get("value")
                        for attr in items[index]
                        if attr.tag == "{http://torznab.com/schemas/2015/feed}attr"
                    }
                    release["language"] = "English" if attrs.get("language") == "English" else None
