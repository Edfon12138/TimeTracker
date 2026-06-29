"""Rule-based classification of windows into activity categories."""
import re

def classify(process: str, window_title: str, rules: list[dict], defaults: dict) -> str:
    """
    Priority:
    1. Rule with matching process AND title_pattern regex
    2. Rule with matching process only
    3. defaults[process_lower]
    4. '其他'
    """
    pl = process.lower()
    tl = window_title.lower()
    title_match = None
    process_match = None

    for r in rules:
        if r["process"].lower() != pl:
            continue
        tp = r.get("title_pattern")
        if tp:
            if re.search(tp.lower(), tl):
                title_match = r["category"]
        elif process_match is None:
            process_match = r["category"]

    if title_match:
        return title_match
    if process_match:
        return process_match
    if pl in defaults:
        return defaults[pl]
    return "其他"

def extract_domain_from_title(window_title: str) -> str | None:
    for sep in [" — ", " · ", " - ", " | ", " – "]:
        if sep in window_title:
            parts = window_title.split(sep)
            if parts[0].strip():
                return parts[0].strip()
    return None

_VIDEO_KEYWORDS = [
    "youtube", "netflix", "bilibili", "twitch", "disneyplus",
    "hbo", "crunchyroll", "plex", "prime video", "hulu",
    "放映", "播放", "视频", "直播", "影视", "追剧",
    "弹幕", "正在播放", "vod", "stream", "mpv",
    "potplayer", "vlc", "完美解码", "kmplayer",
]

def match_video_keywords(title: str) -> bool:
    """Check if a window title suggests video playback."""
    tl = title.lower()
    return any(kw in tl for kw in _VIDEO_KEYWORDS)
