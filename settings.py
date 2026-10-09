import json
import os
import tempfile
import threading
from copy import deepcopy
from pathlib import Path
from typing import Any, Mapping
from urllib.parse import urlsplit

from result_processor import PRESETS, ResultProcessingError, validate_rules

DEFAULT_SETTINGS_PATH = Path("/data/state/settings.json")
SUPPORTED_ENVIRONMENT_OVERRIDES = {
    "DB_AUTO_UPDATE",
    "DB_UPDATE_INTERVAL",
    "ICVDB_RESULT_PRESET",
    "ICVDB_PROWLARR_URL",
    "ICVDB_PROWLARR_API_KEY",
    "PROWLARR_API_KEY",
    "PROWLARR_INDEXER_URL",
}
DEFAULT_SETTINGS = {
    "schema_version": 1,
    "database_update": {
        "enabled": True,
        "interval_seconds": 86400,
    },
    "result_processing": {
        "preset": "unfiltered",
        "custom_rules": [],
        "subtitle_language_correction": False,
    },
    "prowlarr": {
        "url": "",
        "indexer_url": "",
        "api_key": "",
    },
}


class SettingsError(ValueError):
    pass


class SettingsStore:
    """Load defaults, overlay persisted settings, then apply runtime env overrides."""

    def __init__(
        self,
        path: str | Path | None = None,
        environ: Mapping[str, str] | None = None,
    ) -> None:
        self.environ = os.environ if environ is None else environ
        configured_path = self.environ.get("ICVDB_SETTINGS_PATH")
        self.path = Path(path or configured_path or DEFAULT_SETTINGS_PATH)
        self._lock = threading.RLock()

    def load(self) -> dict[str, Any]:
        persisted = self.load_persisted()
        effective = self._apply_environment_overrides(persisted)
        return validate_settings(effective)

    def load_persisted(self) -> dict[str, Any]:
        """Return validated disk settings without runtime environment overrides."""
        with self._lock:
            if not self.path.exists():
                self.save(deepcopy(DEFAULT_SETTINGS))

            try:
                with self.path.open("r", encoding="utf-8") as settings_file:
                    persisted = json.load(settings_file)
            except (OSError, json.JSONDecodeError) as exc:
                raise SettingsError(f"cannot load settings: {exc}") from exc

            return validate_settings(_overlay_defaults(DEFAULT_SETTINGS, persisted))

    def save(self, settings: Any) -> dict[str, Any]:
        validated = validate_settings(settings)
        with self._lock:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            temporary_path = None
            try:
                with tempfile.NamedTemporaryFile(
                    mode="w",
                    encoding="utf-8",
                    dir=self.path.parent,
                    prefix=f".{self.path.name}.",
                    suffix=".tmp",
                    delete=False,
                ) as temporary:
                    temporary_path = Path(temporary.name)
                    json.dump(validated, temporary, indent=2, sort_keys=True)
                    temporary.write("\n")
                    temporary.flush()
                    os.fsync(temporary.fileno())
                os.replace(temporary_path, self.path)
                temporary_path = None
            finally:
                if temporary_path is not None:
                    temporary_path.unlink(missing_ok=True)
        return deepcopy(validated)

    def public(self) -> dict[str, Any]:
        settings = self.load()
        public = deepcopy(settings)
        secret = public["prowlarr"].pop("api_key")
        public["prowlarr"]["api_key_configured"] = bool(secret)
        return public

    def update_public(self, public_settings: Any) -> dict[str, Any]:
        """Persist a complete public settings document without leaking env values."""
        if not isinstance(public_settings, dict):
            raise SettingsError("settings must be an object")
        _require_keys(
            public_settings,
            {"schema_version", "database_update", "result_processing", "prowlarr"},
            "settings",
        )
        prowlarr = public_settings.get("prowlarr")
        _require_object(prowlarr, "prowlarr")
        allowed = {"url", "indexer_url", "api_key", "api_key_configured"}
        unknown = set(prowlarr) - allowed
        required = {"url", "indexer_url"}
        if unknown or not required.issubset(prowlarr):
            raise SettingsError("prowlarr has unknown or missing fields")
        if "api_key_configured" in prowlarr and not isinstance(
            prowlarr["api_key_configured"], bool
        ):
            raise SettingsError("prowlarr.api_key_configured must be a boolean")

        with self._lock:
            persisted = self.load_persisted()
            candidate = deepcopy(public_settings)
            candidate_prowlarr = candidate["prowlarr"]
            candidate_prowlarr.pop("api_key_configured", None)
            if "api_key" not in candidate_prowlarr:
                candidate_prowlarr["api_key"] = persisted["prowlarr"]["api_key"]
            # A GET/PUT round trip must not copy effective environment values
            # into the persisted layer. Environment-owned fields stay untouched.
            if "DB_AUTO_UPDATE" in self.environ:
                candidate["database_update"]["enabled"] = persisted["database_update"]["enabled"]
            if "DB_UPDATE_INTERVAL" in self.environ:
                candidate["database_update"]["interval_seconds"] = persisted["database_update"][
                    "interval_seconds"
                ]
            if "ICVDB_RESULT_PRESET" in self.environ:
                candidate["result_processing"]["preset"] = persisted["result_processing"]["preset"]
            if "ICVDB_PROWLARR_URL" in self.environ:
                candidate_prowlarr["url"] = persisted["prowlarr"]["url"]
            if "PROWLARR_INDEXER_URL" in self.environ:
                candidate_prowlarr["indexer_url"] = persisted["prowlarr"]["indexer_url"]
            self.save(candidate)
        return self.public()

    def update_result_processing(self, processing: Any) -> dict[str, Any]:
        if not isinstance(processing, dict):
            raise SettingsError("result_processing must be an object")
        with self._lock:
            persisted = self.load_persisted()
            persisted["result_processing"] = deepcopy(processing)
            saved = self.save(persisted)
        return deepcopy(saved["result_processing"])

    def _apply_environment_overrides(self, settings: dict[str, Any]) -> dict[str, Any]:
        effective = deepcopy(settings)
        if "DB_AUTO_UPDATE" in self.environ:
            effective["database_update"]["enabled"] = _environment_bool(
                "DB_AUTO_UPDATE",
                self.environ["DB_AUTO_UPDATE"],
            )
        if "DB_UPDATE_INTERVAL" in self.environ:
            effective["database_update"]["interval_seconds"] = _environment_int(
                "DB_UPDATE_INTERVAL",
                self.environ["DB_UPDATE_INTERVAL"],
            )
        if "ICVDB_RESULT_PRESET" in self.environ:
            effective["result_processing"]["preset"] = self.environ["ICVDB_RESULT_PRESET"]
        if "ICVDB_PROWLARR_URL" in self.environ:
            effective["prowlarr"]["url"] = self.environ["ICVDB_PROWLARR_URL"]
        if "ICVDB_PROWLARR_API_KEY" in self.environ:
            effective["prowlarr"]["api_key"] = self.environ["ICVDB_PROWLARR_API_KEY"]
        if "PROWLARR_API_KEY" in self.environ:
            effective["prowlarr"]["api_key"] = self.environ["PROWLARR_API_KEY"]
        if "PROWLARR_INDEXER_URL" in self.environ:
            effective["prowlarr"]["indexer_url"] = self.environ["PROWLARR_INDEXER_URL"]
        return effective


def validate_settings(settings: Any) -> dict[str, Any]:
    if not isinstance(settings, dict):
        raise SettingsError("settings must be an object")
    _require_keys(
        settings,
        {"schema_version", "database_update", "result_processing", "prowlarr"},
        "settings",
    )
    if settings["schema_version"] != 1 or isinstance(settings["schema_version"], bool):
        raise SettingsError("schema_version must be 1")

    database_update = settings["database_update"]
    _require_object(database_update, "database_update")
    _require_keys(database_update, {"enabled", "interval_seconds"}, "database_update")
    if not isinstance(database_update["enabled"], bool):
        raise SettingsError("database_update.enabled must be a boolean")
    interval = database_update["interval_seconds"]
    if not isinstance(interval, int) or isinstance(interval, bool) or not 60 <= interval <= 604800:
        raise SettingsError("database_update.interval_seconds must be between 60 and 604800")

    processing = settings["result_processing"]
    _require_object(processing, "result_processing")
    _require_keys(
        processing, {"preset", "custom_rules", "subtitle_language_correction"}, "result_processing"
    )
    if not isinstance(processing["subtitle_language_correction"], bool):
        raise SettingsError("result_processing.subtitle_language_correction must be a boolean")
    if processing["preset"] not in PRESETS:
        raise SettingsError("result_processing.preset is invalid")
    try:
        rules = validate_rules(processing["custom_rules"])
    except ResultProcessingError as exc:
        raise SettingsError(str(exc)) from exc

    prowlarr = settings["prowlarr"]
    _require_object(prowlarr, "prowlarr")
    _require_keys(prowlarr, {"url", "indexer_url", "api_key"}, "prowlarr")
    for name in ("url", "indexer_url"):
        _validate_optional_http_url(prowlarr[name], f"prowlarr.{name}")
    for name, maximum in (("api_key", 4096),):
        value = prowlarr[name]
        if not isinstance(value, str) or len(value) > maximum:
            raise SettingsError(f"prowlarr.{name} must be a bounded string")

    validated = deepcopy(settings)
    validated["result_processing"]["custom_rules"] = rules
    return validated


def _overlay_defaults(defaults: Any, persisted: Any, path: str = "settings") -> Any:
    if not isinstance(defaults, dict):
        return deepcopy(persisted)
    if not isinstance(persisted, dict):
        return deepcopy(persisted)
    unknown = set(persisted) - set(defaults)
    if unknown:
        raise SettingsError(f"{path} has unknown fields")
    merged = deepcopy(defaults)
    for key, value in persisted.items():
        merged[key] = _overlay_defaults(defaults[key], value, f"{path}.{key}")
    return merged


def _require_object(value: Any, name: str) -> None:
    if not isinstance(value, dict):
        raise SettingsError(f"{name} must be an object")


def _require_keys(value: dict, expected: set[str], name: str) -> None:
    if set(value) != expected:
        raise SettingsError(f"{name} has unknown or missing fields")


def _validate_optional_http_url(value: Any, name: str) -> None:
    if not isinstance(value, str) or len(value) > 2048:
        raise SettingsError(f"{name} must be a bounded URL")
    if not value:
        return
    if value != value.strip():
        raise SettingsError(f"{name} must be an absolute HTTP URL")
    try:
        parsed = urlsplit(value)
        parsed.port
    except ValueError as exc:
        raise SettingsError(f"{name} must be an absolute HTTP URL") from exc
    if (
        parsed.scheme not in {"http", "https"}
        or not parsed.hostname
        or parsed.username is not None
        or parsed.password is not None
    ):
        raise SettingsError(f"{name} must be an absolute HTTP URL without credentials")


def _environment_bool(name: str, value: str) -> bool:
    normalized = value.strip().casefold()
    if normalized == "true":
        return True
    if normalized == "false":
        return False
    raise SettingsError(f"{name} must be true or false")


def _environment_int(name: str, value: str) -> int:
    try:
        return int(value)
    except ValueError as exc:
        raise SettingsError(f"{name} must be an integer") from exc
