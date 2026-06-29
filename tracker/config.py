"""JSON config file read/write with defaults."""
import json
import os
from copy import deepcopy

DEFAULT_CONFIG = {
    "min_duration_sec": 5,
    "idle_timeout_min": 5,
    "retention_days": 90,
    "autostart": False,
    "export_path": "",
    "categories": {
        "工作": {"color": "#7BA78E"},
        "娱乐": {"color": "#D4956B"},
        "浏览": {"color": "#7B9EC7"},
        "通讯": {"color": "#A78BB5"},
        "系统": {"color": "#6B6B6B"},
        "其他": {"color": "#5A5A5A"},
    },
    "rules": [
        {"process": "Code.exe", "title_pattern": None, "category": "工作"},
        {"process": "devenv.exe", "title_pattern": None, "category": "工作"},
        {"process": "WindowsTerminal.exe", "title_pattern": None, "category": "工作"},
        {"process": "chrome.exe", "title_pattern": "GitHub|Jira|Stack Overflow", "category": "工作"},
        {"process": "chrome.exe", "title_pattern": "YouTube|Netflix|Bilibili", "category": "娱乐"},
        {"process": "steam.exe", "title_pattern": None, "category": "娱乐"},
        {"process": "WeChat.exe", "title_pattern": None, "category": "通讯"},
        {"process": "QQ.exe", "title_pattern": None, "category": "通讯"},
        {"process": "explorer.exe", "title_pattern": None, "category": "系统"},
    ],
    "defaults": {
        "chrome.exe": "浏览",
        "msedge.exe": "浏览",
        "firefox.exe": "浏览",
    },
}

def _config_path() -> str:
    return os.path.join(os.path.dirname(os.path.abspath(__file__)), "config.json")

def load_config() -> dict:
    path = _config_path()
    if not os.path.exists(path):
        return deepcopy(DEFAULT_CONFIG)
    with open(path, "r", encoding="utf-8") as f:
        user = json.load(f)
    merged = deepcopy(DEFAULT_CONFIG)
    for key in DEFAULT_CONFIG:
        if key in user:
            merged[key] = user[key]
    return merged

def save_config(config: dict) -> None:
    path = _config_path()
    with open(path, "w", encoding="utf-8") as f:
        json.dump(config, f, ensure_ascii=False, indent=2)
