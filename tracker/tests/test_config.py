import json, os, sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
import config as cfg

def test_default_config_has_required_keys():
    c = cfg.DEFAULT_CONFIG
    assert "min_duration_sec" in c
    assert "categories" in c
    assert "rules" in c

def test_load_config_returns_defaults_when_no_file(monkeypatch):
    monkeypatch.setattr(cfg, "_config_path", lambda: "/nonexistent.json")
    c = cfg.load_config()
    assert c["min_duration_sec"] == 5

def test_save_and_load_roundtrip(monkeypatch, tmp_path):
    p = str(tmp_path / "config.json")
    monkeypatch.setattr(cfg, "_config_path", lambda: p)
    c = cfg.load_config()
    c["min_duration_sec"] = 10
    cfg.save_config(c)
    loaded = cfg.load_config()
    assert loaded["min_duration_sec"] == 10
