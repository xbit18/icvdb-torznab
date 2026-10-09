import json

import pytest

from settings import SettingsError, SettingsStore


def test_first_load_creates_valid_defaults(tmp_path):
    path = tmp_path / "state" / "settings.json"

    settings = SettingsStore(path=path, environ={}).load()

    assert path.exists()
    assert settings["schema_version"] == 1
    assert settings["result_processing"] == {
        "preset": "unfiltered",
        "custom_rules": [],
        "subtitle_language_correction": False,
    }
    assert settings["prowlarr"] == {
        "url": "",
        "indexer_url": "",
        "api_key": "",
    }
    assert json.loads(path.read_text(encoding="utf-8")) == settings


def test_save_load_and_reload(tmp_path):
    path = tmp_path / "settings.json"
    store = SettingsStore(path=path, environ={})
    settings = store.load()
    settings["result_processing"]["preset"] = "italian_only"
    settings["prowlarr"]["url"] = "http://prowlarr:9696"
    settings["prowlarr"]["indexer_url"] = "https://indexer.example/api"
    settings["prowlarr"]["api_key"] = "top-secret"

    store.save(settings)

    assert SettingsStore(path=path, environ={}).load() == settings


def test_partial_persisted_settings_are_overlaid_on_defaults(tmp_path):
    path = tmp_path / "settings.json"
    path.write_text(
        json.dumps({"result_processing": {"preset": "italian_only"}}),
        encoding="utf-8",
    )

    settings = SettingsStore(path=path, environ={}).load()

    assert settings["result_processing"]["preset"] == "italian_only"
    assert settings["result_processing"]["custom_rules"] == []
    assert settings["database_update"]["enabled"] is True


def test_failed_atomic_replace_preserves_previous_file(tmp_path, monkeypatch):
    path = tmp_path / "settings.json"
    store = SettingsStore(path=path, environ={})
    original = store.load()
    changed = store.load()
    changed["result_processing"]["preset"] = "italian_preferred"

    def fail_replace(source, destination):
        raise OSError("replace failed")

    monkeypatch.setattr("settings.os.replace", fail_replace)

    with pytest.raises(OSError, match="replace failed"):
        store.save(changed)

    assert json.loads(path.read_text(encoding="utf-8")) == original
    assert list(tmp_path.glob(".settings.json.*.tmp")) == []


@pytest.mark.parametrize(
    "mutate",
    [
        lambda value: value.update({"future": {}}),
        lambda value: value["result_processing"].update({"preset": "unknown"}),
        lambda value: value["database_update"].update({"interval_seconds": "daily"}),
        lambda value: value["result_processing"]["custom_rules"].append(
            {
                "enabled": True,
                "field": "title",
                "operator": "regex",
                "value": ".*",
                "action": "exclude",
            }
        ),
        lambda value: value["result_processing"]["custom_rules"].append(
            {
                "enabled": True,
                "field": "title",
                "operator": "contains",
                "value": "cam",
                "action": "exclude",
                "score": 50,
            }
        ),
    ],
)
def test_invalid_settings_are_rejected_without_overwrite(tmp_path, mutate):
    path = tmp_path / "settings.json"
    store = SettingsStore(path=path, environ={})
    original = store.load()
    invalid = store.load()
    mutate(invalid)

    with pytest.raises(SettingsError):
        store.save(invalid)

    assert json.loads(path.read_text(encoding="utf-8")) == original


def test_environment_values_override_persisted_values_without_rewriting_them(tmp_path):
    path = tmp_path / "settings.json"
    persisted_store = SettingsStore(path=path, environ={})
    persisted = persisted_store.load()
    persisted["result_processing"]["preset"] = "italian_only"
    persisted_store.save(persisted)

    effective = SettingsStore(
        path=path,
        environ={
            "ICVDB_RESULT_PRESET": "italian_preferred",
            "DB_AUTO_UPDATE": "false",
            "DB_UPDATE_INTERVAL": "3600",
            "ICVDB_PROWLARR_URL": "http://prowlarr:9696",
            "PROWLARR_INDEXER_URL": "https://indexer.example/api",
            "ICVDB_PROWLARR_API_KEY": "runtime-secret",
        },
    ).load()

    assert effective["result_processing"]["preset"] == "italian_preferred"
    assert effective["database_update"] == {
        "enabled": False,
        "interval_seconds": 3600,
    }
    assert effective["prowlarr"]["url"] == "http://prowlarr:9696"
    assert effective["prowlarr"]["indexer_url"] == "https://indexer.example/api"
    assert effective["prowlarr"]["api_key"] == "runtime-secret"
    assert json.loads(path.read_text(encoding="utf-8")) == persisted


def test_invalid_environment_override_is_rejected(tmp_path):
    store = SettingsStore(
        path=tmp_path / "settings.json",
        environ={"DB_AUTO_UPDATE": "sometimes"},
    )

    with pytest.raises(SettingsError, match="DB_AUTO_UPDATE"):
        store.load()


def test_public_settings_mask_saved_and_runtime_secrets(tmp_path):
    path = tmp_path / "settings.json"
    store = SettingsStore(path=path, environ={})
    settings = store.load()
    settings["prowlarr"]["api_key"] = "top-secret"
    store.save(settings)

    public = store.public()

    assert public["prowlarr"] == {
        "url": "",
        "indexer_url": "",
        "api_key_configured": True,
    }
    assert "top-secret" not in json.dumps(public)


def test_runtime_prowlarr_api_key_is_masked_and_never_persisted(tmp_path):
    path = tmp_path / "settings.json"
    store = SettingsStore(
        path=path,
        environ={"PROWLARR_API_KEY": "runtime-only-secret"},
    )

    public = store.public()
    persisted = path.read_text(encoding="utf-8")

    assert public["prowlarr"]["api_key_configured"] is True
    assert "api_key" not in public["prowlarr"]
    assert "runtime-only-secret" not in json.dumps(public)
    assert "runtime-only-secret" not in persisted
    assert json.loads(persisted)["prowlarr"]["api_key"] == ""


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("url", "prowlarr:9696"),
        ("url", "ftp://prowlarr.example"),
        ("url", "http://user:password@prowlarr.example"),
        ("indexer_url", "https:///api"),
        ("indexer_url", "http://indexer.example:invalid/api"),
    ],
)
def test_invalid_configured_prowlarr_urls_are_rejected(tmp_path, field, value):
    store = SettingsStore(path=tmp_path / "settings.json", environ={})
    settings = store.load()
    settings["prowlarr"][field] = value

    with pytest.raises(SettingsError, match=field):
        store.save(settings)


def test_absolute_http_prowlarr_urls_are_valid(tmp_path):
    store = SettingsStore(path=tmp_path / "settings.json", environ={})
    settings = store.load()
    settings["prowlarr"]["url"] = "http://prowlarr:9696"
    settings["prowlarr"]["indexer_url"] = "https://indexer.example/api?t=caps"

    saved = store.save(settings)

    assert saved["prowlarr"]["url"] == "http://prowlarr:9696"
    assert saved["prowlarr"]["indexer_url"] == "https://indexer.example/api?t=caps"


def test_public_update_preserves_replaces_and_clears_persisted_api_key(tmp_path):
    path = tmp_path / "settings.json"
    store = SettingsStore(path=path, environ={})
    persisted = store.load()
    persisted["prowlarr"]["api_key"] = "stored-secret"
    store.save(persisted)

    public = store.public()
    public["prowlarr"]["url"] = "http://prowlarr:9696"
    store.update_public(public)
    assert store.load_persisted()["prowlarr"]["api_key"] == "stored-secret"

    public["prowlarr"]["api_key"] = "replacement-secret"
    store.update_public(public)
    assert store.load_persisted()["prowlarr"]["api_key"] == "replacement-secret"

    public["prowlarr"]["api_key"] = ""
    store.update_public(public)
    assert store.load_persisted()["prowlarr"]["api_key"] == ""


def test_public_update_never_persists_runtime_api_key(tmp_path):
    path = tmp_path / "settings.json"
    store = SettingsStore(
        path=path,
        environ={"PROWLARR_API_KEY": "runtime-secret"},
    )

    public = store.public()
    public["database_update"]["enabled"] = False
    store.update_public(public)

    persisted = path.read_text(encoding="utf-8")
    assert "runtime-secret" not in persisted
    assert store.load_persisted()["prowlarr"]["api_key"] == ""


def test_public_round_trip_never_persists_non_secret_runtime_overrides(tmp_path):
    store = SettingsStore(
        path=tmp_path / "settings.json",
        environ={
            "DB_AUTO_UPDATE": "false",
            "DB_UPDATE_INTERVAL": "3600",
            "ICVDB_RESULT_PRESET": "italian_only",
            "ICVDB_PROWLARR_URL": "http://runtime-prowlarr:9696",
            "PROWLARR_INDEXER_URL": "http://runtime-indexer:8000/api",
        },
    )

    store.update_public(store.public())
    persisted = store.load_persisted()

    assert persisted["database_update"] == {
        "enabled": True,
        "interval_seconds": 86400,
    }
    assert persisted["result_processing"]["preset"] == "unfiltered"
    assert persisted["prowlarr"]["url"] == ""
    assert persisted["prowlarr"]["indexer_url"] == ""


def test_public_update_rejects_unknown_fields_without_overwrite(tmp_path):
    path = tmp_path / "settings.json"
    store = SettingsStore(path=path, environ={})
    original = store.load_persisted()
    public = store.public()
    public["prowlarr"]["unexpected"] = True

    with pytest.raises(SettingsError, match="unknown"):
        store.update_public(public)

    assert store.load_persisted() == original


def test_subtitle_language_correction_persists_and_defaults_off(tmp_path):
    path = tmp_path / "settings.json"
    store = SettingsStore(path=path, environ={})
    settings = store.load()
    assert settings["result_processing"]["subtitle_language_correction"] is False

    settings["result_processing"]["subtitle_language_correction"] = True
    store.save(settings)
    assert (
        SettingsStore(path=path, environ={}).load()["result_processing"][
            "subtitle_language_correction"
        ]
        is True
    )

    # Existing installations without the field are migrated in memory.
    old = json.loads(path.read_text(encoding="utf-8"))
    old["result_processing"].pop("subtitle_language_correction")
    path.write_text(json.dumps(old), encoding="utf-8")
    assert (
        SettingsStore(path=path, environ={}).load()["result_processing"][
            "subtitle_language_correction"
        ]
        is False
    )


def test_subtitle_language_correction_rejects_non_bool(tmp_path):
    store = SettingsStore(path=tmp_path / "settings.json", environ={})
    settings = store.load()
    settings["result_processing"]["subtitle_language_correction"] = "true"
    with pytest.raises(SettingsError, match="subtitle_language_correction"):
        store.save(settings)
