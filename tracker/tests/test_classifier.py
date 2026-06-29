import os, sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
import classifier

RULES = [
    {"process": "Code.exe", "title_pattern": None, "category": "工作"},
    {"process": "chrome.exe", "title_pattern": "GitHub|Jira|Stack Overflow", "category": "工作"},
    {"process": "chrome.exe", "title_pattern": "YouTube|Netflix|Bilibili", "category": "娱乐"},
    {"process": "WeChat.exe", "title_pattern": None, "category": "通讯"},
]
DEFAULTS = {"chrome.exe": "浏览", "msedge.exe": "浏览"}

def test_exact_process_match():
    assert classifier.classify("Code.exe", "x", RULES, DEFAULTS) == "工作"

def test_title_pattern_match_wins():
    assert classifier.classify("chrome.exe", "GitHub PR review", RULES, DEFAULTS) == "工作"

def test_title_no_match_falls_to_default():
    assert classifier.classify("chrome.exe", "Some random site", RULES, DEFAULTS) == "浏览"

def test_default_only():
    assert classifier.classify("msedge.exe", "x", RULES, DEFAULTS) == "浏览"

def test_unknown_process():
    assert classifier.classify("unknown.exe", "x", RULES, DEFAULTS) == "其他"

def test_title_priority_over_process():
    rules = [
        {"process": "chrome.exe", "title_pattern": None, "category": "浏览"},
        {"process": "chrome.exe", "title_pattern": "GitHub", "category": "工作"},
    ]
    assert classifier.classify("chrome.exe", "GitHub test", rules, {}) == "工作"
    assert classifier.classify("chrome.exe", "random", rules, {}) == "浏览"

def test_case_insensitive():
    assert classifier.classify("CODE.EXE", "x", RULES, DEFAULTS) == "工作"

def test_extract_domain():
    d = classifier.extract_domain_from_title("GitHub - Google Chrome")
    assert d is not None
