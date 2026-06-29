"""JSON config file read/write with defaults."""
import json
import os, sys
from copy import deepcopy

def _base_dir():
    if getattr(sys, 'frozen', False):
        return os.path.dirname(sys.executable)
    return os.path.dirname(os.path.abspath(__file__))

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
        # ── 开发工具 ──
        {"process": "Code.exe", "title_pattern": None, "category": "工作"},
        {"process": "devenv.exe", "title_pattern": None, "category": "工作"},
        {"process": "idea64.exe", "title_pattern": None, "category": "工作"},
        {"process": "pycharm64.exe", "title_pattern": None, "category": "工作"},
        {"process": "webstorm64.exe", "title_pattern": None, "category": "工作"},
        {"process": "goland64.exe", "title_pattern": None, "category": "工作"},
        {"process": "clion64.exe", "title_pattern": None, "category": "工作"},
        {"process": "rider64.exe", "title_pattern": None, "category": "工作"},
        {"process": "AndroidStudio.exe", "title_pattern": None, "category": "工作"},
        {"process": "sublime_text.exe", "title_pattern": None, "category": "工作"},
        {"process": "notepad++.exe", "title_pattern": None, "category": "工作"},
        {"process": "terminal.exe", "title_pattern": None, "category": "工作"},
        {"process": "WindowsTerminal.exe", "title_pattern": None, "category": "工作"},
        {"process": "cmd.exe", "title_pattern": None, "category": "工作"},
        {"process": "powershell.exe", "title_pattern": None, "category": "工作"},
        {"process": "windterm.exe", "title_pattern": None, "category": "工作"},
        {"process": "putty.exe", "title_pattern": None, "category": "工作"},
        {"process": "git-bash.exe", "title_pattern": None, "category": "工作"},
        {"process": "sourcetree.exe", "title_pattern": None, "category": "工作"},
        {"process": "githubdesktop.exe", "title_pattern": None, "category": "工作"},
        {"process": "postman.exe", "title_pattern": None, "category": "工作"},
        {"process": "insomnia.exe", "title_pattern": None, "category": "工作"},

        # ── Office 办公 ──
        {"process": "WINWORD.EXE", "title_pattern": None, "category": "工作"},
        {"process": "EXCEL.EXE", "title_pattern": None, "category": "工作"},
        {"process": "POWERPNT.EXE", "title_pattern": None, "category": "工作"},
        {"process": "OUTLOOK.EXE", "title_pattern": None, "category": "工作"},
        {"process": "ONENOTE.EXE", "title_pattern": None, "category": "工作"},
        {"process": "MSACCESS.EXE", "title_pattern": None, "category": "工作"},
        {"process": "WINPROJ.EXE", "title_pattern": None, "category": "工作"},
        {"process": "VISIO.EXE", "title_pattern": None, "category": "工作"},
        {"process": "Acrobat.exe", "title_pattern": None, "category": "工作"},
        {"process": "AcroRd32.exe", "title_pattern": None, "category": "工作"},
        {"process": "foxitreader.exe", "title_pattern": None, "category": "工作"},
        {"process": "obsidian.exe", "title_pattern": None, "category": "工作"},
        {"process": "Typora.exe", "title_pattern": None, "category": "工作"},
        {"process": "Notion.exe", "title_pattern": None, "category": "工作"},

        # ── 设计工具 ──
        {"process": "photoshop.exe", "title_pattern": None, "category": "工作"},
        {"process": "illustrator.exe", "title_pattern": None, "category": "工作"},
        {"process": "figma.exe", "title_pattern": None, "category": "工作"},
        {"process": "xd.exe", "title_pattern": None, "category": "工作"},
        {"process": "gimp.exe", "title_pattern": None, "category": "工作"},
        {"process": "blender.exe", "title_pattern": None, "category": "工作"},
        {"process": "3dsmax.exe", "title_pattern": None, "category": "工作"},
        {"process": "maya.exe", "title_pattern": None, "category": "工作"},
        {"process": "sketchup.exe", "title_pattern": None, "category": "工作"},

        # ── 浏览器（按标题匹配细分） ──
        {"process": "chrome.exe", "title_pattern": "GitHub|Jira|Stack Overflow|Confluence|Notion|Linear|Figma|Code Review|Pull Request|MDN|docs\\.", "category": "工作"},
        {"process": "chrome.exe", "title_pattern": "YouTube|Netflix|Bilibili|Twitch|Disney\\+|HBO|Crunchyroll|Plex|Hulu|Prime Video|Spotify|网易云|QQ音乐", "category": "娱乐"},
        {"process": "chrome.exe", "title_pattern": "Reddit|知乎|微博|贴吧|小红书|抖音|哔哩哔哩|Twitter|X\\.com|Instagram|Facebook|TikTok", "category": "浏览"},
        {"process": "chrome.exe", "title_pattern": "Gmail|Outlook|Mail|收件箱", "category": "通讯"},
        {"process": "msedge.exe", "title_pattern": "GitHub|Jira|Stack Overflow|Confluence|Notion|Linear|Code Review", "category": "工作"},
        {"process": "msedge.exe", "title_pattern": "YouTube|Netflix|Bilibili|Twitch|Disney\\+|HBO|Spotify|网易云", "category": "娱乐"},
        {"process": "msedge.exe", "title_pattern": "Reddit|知乎|微博|贴吧|小红书|抖音|Twitter|Instagram|Facebook", "category": "浏览"},
        {"process": "msedge.exe", "title_pattern": "Gmail|Outlook|Mail|收件箱", "category": "通讯"},
        {"process": "firefox.exe", "title_pattern": "GitHub|Jira|Stack Overflow|Confluence", "category": "工作"},
        {"process": "firefox.exe", "title_pattern": "YouTube|Netflix|Bilibili|Twitch", "category": "娱乐"},

        # ── 通讯 ──
        {"process": "WeChat.exe", "title_pattern": None, "category": "通讯"},
        {"process": "Weixin.exe", "title_pattern": None, "category": "通讯"},
        {"process": "QQ.exe", "title_pattern": None, "category": "通讯"},
        {"process": "TIM.exe", "title_pattern": None, "category": "通讯"},
        {"process": "discord.exe", "title_pattern": None, "category": "通讯"},
        {"process": "slack.exe", "title_pattern": None, "category": "通讯"},
        {"process": "telegram.exe", "title_pattern": None, "category": "通讯"},
        {"process": "MicrosoftTeams.exe", "title_pattern": None, "category": "通讯"},
        {"process": "Teams.exe", "title_pattern": None, "category": "通讯"},
        {"process": "dingtalk.exe", "title_pattern": None, "category": "通讯"},
        {"process": "DingTalk.exe", "title_pattern": None, "category": "通讯"},
        {"process": "feishu.exe", "title_pattern": None, "category": "通讯"},
        {"process": "Lark.exe", "title_pattern": None, "category": "通讯"},
        {"process": "zoom.exe", "title_pattern": None, "category": "通讯"},
        {"process": "skype.exe", "title_pattern": None, "category": "通讯"},
        {"process": "whatsapp.exe", "title_pattern": None, "category": "通讯"},

        # ── 游戏 ──
        {"process": "steam.exe", "title_pattern": None, "category": "娱乐"},
        {"process": "Steam.exe", "title_pattern": None, "category": "娱乐"},
        {"process": "epicgameslauncher.exe", "title_pattern": None, "category": "娱乐"},
        {"process": "battle.net.exe", "title_pattern": None, "category": "娱乐"},
        {"process": "origin.exe", "title_pattern": None, "category": "娱乐"},
        {"process": "XboxPcApp.exe", "title_pattern": None, "category": "娱乐"},
        {"process": "GameBar.exe", "title_pattern": None, "category": "娱乐"},

        # ── 影音播放 ──
        {"process": "potplayer.exe", "title_pattern": None, "category": "娱乐"},
        {"process": "vlc.exe", "title_pattern": None, "category": "娱乐"},
        {"process": "mpv.exe", "title_pattern": None, "category": "娱乐"},
        {"process": "wmplayer.exe", "title_pattern": None, "category": "娱乐"},
        {"process": "spotify.exe", "title_pattern": None, "category": "娱乐"},
        {"process": "cloudmusic.exe", "title_pattern": None, "category": "娱乐"},
        {"process": "QQMusic.exe", "title_pattern": None, "category": "娱乐"},
        {"process": "KuGou.exe", "title_pattern": None, "category": "娱乐"},

        # ── 系统 ──
        {"process": "explorer.exe", "title_pattern": None, "category": "系统"},
        {"process": "Taskmgr.exe", "title_pattern": None, "category": "系统"},
        {"process": "mmc.exe", "title_pattern": None, "category": "系统"},
        {"process": "regedit.exe", "title_pattern": None, "category": "系统"},
        {"process": "msconfig.exe", "title_pattern": None, "category": "系统"},
        {"process": "Calculator.exe", "title_pattern": None, "category": "系统"},
        {"process": "Notepad.exe", "title_pattern": None, "category": "系统"},
        {"process": "SnippingTool.exe", "title_pattern": None, "category": "系统"},
        {"process": "osk.exe", "title_pattern": None, "category": "系统"},
        {"process": "Magnify.exe", "title_pattern": None, "category": "系统"},
        {"process": "conhost.exe", "title_pattern": None, "category": "系统"},
    ],
    "defaults": {
        "chrome.exe": "浏览",
        "msedge.exe": "浏览",
        "firefox.exe": "浏览",
    },
}

def _config_path() -> str:
    return os.path.join(_base_dir(), "config.json")

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
