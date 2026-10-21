from dualsync.services.config import AppSettings, ConfigStore


def test_round_trip_and_limits(tmp_path):
    store = ConfigStore(tmp_path / "settings.json")
    settings = AppSettings(max_outputs=9, selected_endpoint_ids=["one"])
    store.save(settings)
    loaded = store.load()
    assert loaded.max_outputs == 5
    assert loaded.selected_endpoint_ids == ["one"]


def test_invalid_config_is_quarantined(tmp_path):
    path = tmp_path / "settings.json"
    path.write_text("{broken", "utf-8")
    loaded = ConfigStore(path).load()
    assert loaded.mode == "Balanced"
    assert (tmp_path / "settings.invalid.json").exists()


def test_output_limit_has_two_to_five_slots(tmp_path):
    store = ConfigStore(tmp_path / "settings.json")
    store.save(AppSettings(max_outputs=1))
    assert store.load().max_outputs == 2
