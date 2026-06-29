# 空闲追踪 + 交互时间轴 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task.

**Goal:** 将空闲/视频时间纳入统计，并在统计页面新增可缩放拖拽的交互时间轴

**Architecture:** 空闲会话仅存内存（idle_detector 中），不落库；stats_html.generate() 时合并到嵌入数据中；时间轴组件为纯 DOM/CSS/JS，不依赖第三方库

**Tech Stack:** Python 3.12+, Windows ctypes, PySide6, SQLite, Chart.js (已有), pure JS DOM

**Python venv:** `d:/repos/我的/venv/Scripts/python`（从 tracker 目录为 `../venv/Scripts/python`）

---

## File Structure

| 文件 | 类型 | 职责 |
|------|------|------|
| `tracker/classifier.py` | 修改 | 新增 `match_video_keywords(title)` |
| `tracker/idle_detector.py` | 修改 | 会话跟踪、get_idle_sessions/clear_idle_sessions、回调传参 |
| `tracker/monitor.py` | 修改 | 新增 `get_current_window()` |
| `tracker/main.py` | 修改 | 更新空闲回调 |
| `tracker/stats_html.py` | 修改 | 数据合并 + HTML/JS/CSS 时间轴 |
| `tracker/tests/test_classifier.py` | 修改 | 测试视频关键词匹配 |
| `tracker/tests/test_idle_detector.py` | 新建 | 测试空闲会话逻辑 |

---

### Task 1: 视频关键词检测函数

**Files:**
- Modify: `tracker/classifier.py`
- Test: `tracker/tests/test_classifier.py`

**Interfaces:**
- Produces: `classifier.match_video_keywords(title: str) -> bool`

- [ ] **Step 1: 添加视频关键词常量 + 测试**

新增函数 `match_video_keywords`，检测窗口标题是否含视频关键词。

```python
# tracker/tests/test_classifier.py 末尾追加

def test_match_video_youtube():
    assert classifier.match_video_keywords("YouTube - Google Chrome")

def test_match_video_bilibili():
    assert classifier.match_video_keywords("Bilibili - 一些视频")

def test_match_video_netflix():
    assert classifier.match_video_keywords("Netflix - 剧集名")

def test_match_video_chinese():
    assert classifier.match_video_keywords("正在播放：电影名")
    assert classifier.match_video_keywords("追剧 - 视频播放器")

def test_no_match_generic():
    assert not classifier.match_video_keywords("GitHub PR review")
    assert not classifier.match_video_keywords("Word文档")

def test_no_match_case_insensitive():
    assert classifier.match_video_keywords("youtube - test")
```

- [ ] **Step 2: 运行测试确认失败**

```bash
cd d:/repos/我的/tracker && ../venv/Scripts/python -m pytest tests/test_classifier.py::test_match_video_youtube -v
```
Expected: `FAILED` — `AttributeError: module 'classifier' has no attribute 'match_video_keywords'`

- [ ] **Step 3: 实现 match_video_keywords**

在 `tracker/classifier.py` 末尾添加：

```python
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
```

- [ ] **Step 4: 运行测试确认通过**

```bash
cd d:/repos/我的/tracker && ../venv/Scripts/python -m pytest tests/test_classifier.py -v
```
Expected: `PASSED`（全部通过，包括已有的测试 + 新增的 6 个）

- [ ] **Step 5: 提交**

```bash
cd d:/repos/我的 && git add tracker/classifier.py tracker/tests/test_classifier.py
git commit -m "feat: add match_video_keywords for video playback detection"
```

---

### Task 2: 空闲会话跟踪 + get_current_window

**Files:**
- Modify: `tracker/monitor.py` — 新增 `get_current_window()`
- Modify: `tracker/idle_detector.py` — 会话跟踪、回调签名变更、get/clear 函数
- Test: `tracker/tests/test_idle_detector.py`（新建）

**Interfaces:**
- Consumes: `monitor.get_current_window() -> tuple[str, str]`
- Produces: `idle_detector.get_idle_sessions() -> list[dict]`
- Produces: `idle_detector.clear_idle_sessions() -> None`
- Callback: `on_idle(session: dict)`, `on_resume(session: dict)` — session 为 `{started_at, ended_at, process, window_title, is_video, category}`

- [ ] **Step 1: 在 monitor.py 新增 get_current_window**

在 `tracker/monitor.py` 末尾添加：

```python
def get_current_window():
    """Return (process_name, window_title) of the current foreground window."""
    hwnd = user32.GetForegroundWindow()
    if not hwnd:
        return ("", "")
    return (_get_process_name(hwnd), _get_window_title(hwnd))
```

- [ ] **Step 2: 重写 idle_detector.py**

完整替换为会话跟踪版本：

```python
"""Idle detection using GetLastInputInfo. Tracks idle session start/end + foreground window."""
import ctypes, ctypes.wintypes, threading, time

class LASTINPUTINFO(ctypes.Structure):
    _fields_ = [("cbSize", ctypes.wintypes.UINT), ("dwTime", ctypes.wintypes.DWORD)]

user32 = ctypes.windll.user32
_idle = False; _timeout_ms = 5 * 60 * 1000; _running = False
_on_idle = None; _on_resume = None
_idle_sessions: list[dict] = []
_current_session: dict | None = None

def _get_idle_ms() -> int:
    lii = LASTINPUTINFO(); lii.cbSize = ctypes.sizeof(LASTINPUTINFO)
    user32.GetLastInputInfo(ctypes.byref(lii))
    return ctypes.windll.kernel32.GetTickCount() - lii.dwTime

def _get_foreground_info():
    """Get (process, window_title, is_video) for the current foreground window."""
    try:
        from monitor import get_current_window
    except ImportError:
        return ("", "", False)
    process, title = get_current_window()
    if not process:
        return ("", "", False)
    try:
        from classifier import match_video_keywords
        is_video = match_video_keywords(title)
    except ImportError:
        is_video = False
    return (process, title, is_video)

def _loop():
    global _idle, _current_session
    while _running:
        ms = _get_idle_ms()
        if ms > _timeout_ms and not _idle:
            # Transition: active → idle
            process, title, is_video = _get_foreground_info()
            category = "视频" if is_video else "空闲"
            _current_session = {
                "started_at": time.time(),
                "ended_at": None,
                "process": process,
                "window_title": title,
                "is_video": is_video,
                "category": category,
            }
            _idle = True
            if _on_idle:
                _on_idle(_current_session)
        elif ms < _timeout_ms and _idle:
            # Transition: idle → active
            if _current_session is not None:
                _current_session["ended_at"] = time.time()
                _idle_sessions.append(_current_session)
                saved = _current_session
                _current_session = None
                if _on_resume:
                    _on_resume(saved)
            _idle = False
        time.sleep(30)

def start_idle_detector(on_idle, on_resume, timeout_min=5):
    global _on_idle, _on_resume, _timeout_ms, _running, _idle, _idle_sessions, _current_session
    _on_idle = on_idle; _on_resume = on_resume
    _timeout_ms = timeout_min * 60 * 1000
    _idle = False; _running = True; _idle_sessions = []; _current_session = None
    t = threading.Thread(target=_loop, daemon=True); t.start()

def stop_idle_detector():
    global _running; _running = False

def is_idle() -> bool:
    return _idle

def get_idle_sessions() -> list[dict]:
    """Return all completed idle sessions. Each includes started_at, ended_at, duration, etc."""
    result = list(_idle_sessions)
    # Include the current ongoing session if idle
    if _idle and _current_session is not None:
        s = dict(_current_session)
        s["ended_at"] = time.time()
        result.append(s)
    # Add computed duration and filter to today
    today_start = time.mktime(time.localtime()[:3] + (0, 0, 0, 0, 0, 0))
    today_end = today_start + 86400
    for s in result:
        s["duration"] = int(s["ended_at"] - s["started_at"])
    return [s for s in result if s["started_at"] >= today_start and s["started_at"] < today_end]

def clear_idle_sessions():
    global _idle_sessions, _current_session
    _idle_sessions = []; _current_session = None
```

- [ ] **Step 3: 创建 idle_detector 测试**

```python
# tracker/tests/test_idle_detector.py
"""Tests for idle_detector session tracking (mocked)."""
import os, sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
import time
from unittest.mock import patch, MagicMock
import idle_detector

def test_get_idle_sessions_with_completed_sessions():
    idle_detector._idle_sessions = []
    idle_detector._current_session = None
    idle_detector._idle = False
    
    # Simulate two completed idle sessions
    now = time.time()
    idle_detector._idle_sessions = [
        {"started_at": now - 7200, "ended_at": now - 3600, "duration": 3600, "category": "空闲", "is_video": False, "process": "", "window_title": ""},
        {"started_at": now - 1800, "ended_at": now - 900, "duration": 900, "category": "视频", "is_video": True, "process": "chrome.exe", "window_title": "YouTube"},
    ]
    sessions = idle_detector.get_idle_sessions()
    assert len(sessions) == 2
    assert sessions[0]["category"] == "空闲"
    assert sessions[1]["category"] == "视频"

def test_clear_idle_sessions():
    idle_detector._idle_sessions = [{"test": "data"}]
    idle_detector._current_session = {"test": "current"}
    idle_detector.clear_idle_sessions()
    assert idle_detector._idle_sessions == []
    assert idle_detector._current_session is None
```

- [ ] **Step 4: 运行测试**

```bash
cd d:/repos/我的/tracker && ../venv/Scripts/python -m pytest tests/test_idle_detector.py -v
```
Expected: `PASSED`（2 个测试通过）

```bash
cd d:/repos/我的/tracker && ../venv/Scripts/python -m pytest tests/ -v
```
Expected: 全部通过（原有 classifier 测试 + 新 idle_detector 测试）

- [ ] **Step 5: 提交**

```bash
cd d:/repos/我的 && git add tracker/monitor.py tracker/idle_detector.py tracker/tests/test_idle_detector.py
git commit -m "feat: add idle session tracking and get_current_window"
```

---

### Task 3: Main.py 回调适配

**Files:**
- Modify: `tracker/main.py`

**Interfaces:**
- Consumes: `idle_detector.start_idle_detector(on_idle, on_resume, timeout_min)` — 回调现在传 session dict

- [ ] **Step 1: 更新 idle 回调**

修改 `tracker/main.py` 中 `TimeTracker.__init__` 和回调方法：

第 27-28 行，`start_idle_detector` 调用改为：
```python
idle_detector.start_idle_detector(on_idle=self._on_idle, on_resume=self._on_resume,
                                  timeout_min=self._config.get("idle_timeout_min", 5))
```

第 41-42 行，回调改为接受 session 参数（实际上只需要存储，但保持签名兼容）：
```python
def _on_idle(self, session=None): pass
def _on_resume(self, session=None): pass
```

- [ ] **Step 2: 验证代码可运行**

```bash
cd d:/repos/我的/tracker && ../venv/Scripts/python -c "from idle_detector import start_idle_detector, stop_idle_detector, get_idle_sessions; print('Import OK')"
```

- [ ] **Step 3: 提交**

```bash
cd d:/repos/我的 && git add tracker/main.py
git commit -m "fix: update idle callbacks to accept session parameter"
```

---

### Task 4: 统计数据合并

**Files:**
- Modify: `tracker/stats_html.py` — `generate()` 函数中合并空闲会话

- [ ] **Step 1: 在 generate() 开头读取空闲会话**

在 `tracker/stats_html.py` 的 `generate()` 函数中，第 37 行 `today = ...` 之后添加：

```python
import idle_detector

def generate():
    today = dt_date.today().isoformat()
    ws = (dt_date.today() - timedelta(days=dt_date.today().weekday())).isoformat()
    ms = dt_date.today().replace(day=1).isoformat()

    # Merge idle/video sessions into stats
    idle_sessions = idle_detector.get_idle_sessions()
    # ... rest continues
```

- [ ] **Step 2: 添加空闲数据合并逻辑**

在 `dp` 构建之后、`conn = sqlite3.connect(...)` 之前，添加：

```python
    # ── Merge idle/video sessions into stats ──
    idle_cat_today = {"空闲": 0, "视频": 0}
    idle_timeline = []
    for s in idle_sessions:
        cat = s["category"]
        dur = s["duration"]
        idle_cat_today[cat] = idle_cat_today.get(cat, 0) + dur
        idle_timeline.append({
            "process": s["process"] or "(无)",
            "window_title": s["window_title"] or (f"[{cat}]" if cat == "视频" else "[无操作]"),
            "category": cat,
            "color": "#6B7280" if cat == "空闲" else "#8B5CF6",
            "started_at": time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(s["started_at"])),
            "duration": dur,
            "icon_uri": _icon_svg("空"[0] if cat == "空闲" else "视", "#6B7280" if cat == "空闲" else "#8B5CF6"),
        })

    # Merge into today's category stats
    for cat, secs in idle_cat_today.items():
        if secs > 0:
            dp["today"]["cat"].append({"label": cat, "value": secs, "color": "#6B7280" if cat == "空闲" else "#8B5CF6", "hk": cat, "type": "category"})

    # Merge into week/month (only today's data, since idle sessions are memory-only)
    for rn in ("week", "month"):
        for cat, secs in idle_cat_today.items():
            if secs > 0:
                existing = [x for x in dp[rn]["cat"] if x["label"] == cat]
                if existing:
                    existing[0]["value"] += secs
                else:
                    dp[rn]["cat"].append({"label": cat, "value": secs, "color": "#6B7280" if cat == "空闲" else "#8B5CF6", "hk": cat, "type": "category"})

    # Merge idle sessions into timeline (sorted by time)
    dp["timeline"].extend(idle_timeline)
    dp["timeline"].sort(key=lambda x: x.get("started_at", ""))
```

添加 `import time` 到文件头部。

- [ ] **Step 3: 验证不报错**

```bash
cd d:/repos/我的/tracker && ../venv/Scripts/python -c "import stats_html; print('Import OK')"
```

- [ ] **Step 4: 提交**

```bash
cd d:/repos/我的 && git add tracker/stats_html.py
git commit -m "feat: merge idle/video sessions into stats page data"
```

---

### Task 5: 时间轴可视化组件

**Files:**
- Modify: `tracker/stats_html.py` — HTML 模板（`HTML_TEMPLATE` 常量）新增时间轴 tab + 可视化组件

- [ ] **Step 1: HTML 结构修改：新增时间轴 tab**

在 `tracker/stats_html.py` 的 `HTML_TEMPLATE` 中，修改顶部 tab 栏（第 172-177 行）：

```html
  <div class="tabs" id="timeTabs">
    <div class="tab active" data-r="today">今日</div>
    <div class="tab" data-r="week">本周</div>
    <div class="tab" data-r="month">本月</div>
    <div class="tab" data-r="timeline">时间轴</div>
    <div class="tab-spacer"></div>
    <button class="btn-gear" id="gearBtn" title="设置">&#9881;</button>
  </div>
```

- [ ] **Step 2: HTML 结构修改：时间轴区域**

在 `<div class="content">` 内部，将现有 `<div class="main">` 和 timeline/footer 用 `#statsView` 包裹，并新增 `#timelineView`：

替换第 180 行 `<div class="main">` 之前到第 197 行 `</div>`（.content 的闭合）之间的内容为：

```html
    <div id="statsView">
      <div class="toolbar">
        <span class="tl">视图</span>
        <div class="tg"><button class="tb active" data-v="cat">按分类</button><button class="tb" data-v="prog">按程序</button></div>
        <span class="tl">图表</span>
        <div class="tg"><button class="tb active" data-c="donut">饼图</button><button class="tb" data-c="bar">柱状图</button></div>
        <div class="spacer"></div>
        <div class="bread" id="bread" style="display:none"><span id="breadBack">&#8592; 返回全部</span></div>
      </div>
      <div class="main">
        <div class="chart-box"><canvas id="chartCanvas"></canvas></div>
        <div class="breakdown" id="breakdownList"></div>
      </div>
      <div class="sl">时间线</div>
      <div id="timeline"></div>
      <div class="footer">
        <button class="btn" id="exportBtn">导出 CSV</button>
      </div>
    </div>

    <!-- Timeline tab content -->
    <div id="timelineView" style="display:none">
      <div class="tl-container">
        <div class="tl-header">
          <div class="tl-ruler" id="tlRuler"></div>
        </div>
        <div class="tl-body" id="tlBody">
          <div class="tl-track" id="tlTrack"></div>
        </div>
        <div class="tl-footer">
          <span class="tl-zoom-label" id="tlZoomLabel">24h 总览 (1×)</span>
          <div class="tl-zoom-controls">
            <button class="tb" id="tlZoomOut">−</button>
            <input type="range" id="tlZoomSlider" min="1" max="16" step="0.25" value="1">
            <button class="tb" id="tlZoomIn">+</button>
          </div>
        </div>
      </div>
    </div>
```

- [ ] **Step 3: 添加时间轴 CSS**

在 `<style>` 块末尾（第 168 行之前）、`</style>` 之前添加：

```css
/* ── Timeline view ── */
.tl-container{width:100%;user-select:none}
.tl-header{position:relative;height:30px;margin-bottom:4px;overflow:hidden}
.tl-ruler{position:absolute;left:0;top:0;height:30px;width:2400px;transform-origin:left center;border-bottom:1px solid #2E3039}
.tl-ruler .rk{position:absolute;top:18px;font-size:10px;color:#5E5A54;transform:translateX(-50%);white-space:nowrap}
.tl-ruler .rk::before{content:'';position:absolute;top:-14px;left:50%;width:1px;height:10px;background:#2E3039}
.tl-ruler .rk.major::before{height:14px;top:-18px}
.tl-body{position:relative;height:180px;overflow:hidden;border-radius:6px;background:#1A1C21;cursor:grab;border:1px solid #2E3039}
.tl-body:active{cursor:grabbing}
.tl-track{position:absolute;left:0;top:0;height:100%;width:2400px;transform-origin:left center;will-change:transform}
.tl-block{position:absolute;height:42px;border-radius:4px;top:50%;transform:translateY(-50%);cursor:pointer;overflow:hidden;transition:opacity .12s;border:1px solid rgba(255,255,255,.06)}
.tl-block:hover{opacity:.85;border-color:rgba(255,255,255,.2)}
.tl-block .bl{position:absolute;left:6px;right:6px;top:4px;font-size:11px;color:rgba(255,255,255,.9);white-space:nowrap;overflow:hidden;text-overflow:ellipsis;pointer-events:none;line-height:1.2}
.tl-block .bs{position:absolute;left:6px;right:6px;bottom:4px;font-size:9px;color:rgba(255,255,255,.6);white-space:nowrap;overflow:hidden;text-overflow:ellipsis;pointer-events:none;line-height:1.2}
.tl-block.small .bl{font-size:9px;top:50%;transform:translateY(-50%)}
.tl-block.small .bs{display:none}
.tl-block.tiny{min-width:2px}
.tl-block.tiny .bl,.tl-block.tiny .bs{display:none}
.tl-footer{display:flex;align-items:center;justify-content:space-between;margin-top:8px}
.tl-zoom-label{font-size:11px;color:#5E5A54}
.tl-zoom-controls{display:flex;align-items:center;gap:8px}
.tl-zoom-controls input[type=range]{width:100px;height:4px;-webkit-appearance:none;appearance:none;background:#2E3039;border-radius:2px;outline:none}
.tl-zoom-controls input[type=range]::-webkit-slider-thumb{-webkit-appearance:none;width:14px;height:14px;border-radius:50%;background:#D4956B;cursor:pointer;border:none}
/* Tooltip for timeline blocks */
.tl-tooltip{position:fixed;background:#24262E;border:1px solid #2E3039;border-radius:6px;padding:8px 12px;font-size:12px;color:#EAE4D9;pointer-events:none;z-index:1000;max-width:280px;box-shadow:0 4px 12px rgba(0,0,0,.4);display:none}
.tl-tooltip .tt-cat{display:inline-block;padding:1px 8px;border-radius:3px;font-size:10px;font-weight:500;margin-bottom:4px}
.tl-tooltip .tt-row{margin:2px 0;display:flex;justify-content:space-between;gap:16px}
.tl-tooltip .tt-label{color:#9B958A}
```

- [ ] **Step 4: 添加时间轴 JavaScript**

替换第 384 行 `function refresh(){renderChart();renderList();renderTL();}` 及之后到第 443 行 `refresh();` 之前的 JS（注意保留现有函数的完整性），在文件末尾 `refresh();` 之前，新增时间轴相关 JS：

查找 `function refresh(){renderChart();renderList();renderTL();}` 并把 `refresh` 改为同时处理 tab 切换。

⚠️ **重要：替换而非追加。** 模板原有一段 `document.getElementById('timeTabs').addEventListener('click', ...)` 代码（约第 386-391 行），需要将其**整体替换**为下面这段新代码（不是追加在你旁边）。删除原 handler，粘贴新 handler：

```javascript
/* ── Time range switching — also handles timeline tab ── */
document.getElementById('timeTabs').addEventListener('click',function(e){
  var t=e.target.closest('.tab');if(!t||!t.dataset.r)return;
  document.querySelectorAll('#timeTabs .tab').forEach(function(x){x.classList.remove('active');});
  t.classList.add('active');
  if(t.dataset.r==='timeline'){
    document.getElementById('statsView').style.display='none';
    document.getElementById('timelineView').style.display='block';
    renderTimelineChart();
  }else{
    document.getElementById('statsView').style.display='';
    document.getElementById('timelineView').style.display='none';
    state.range=t.dataset.r;state.drill=null;state.hlKey=null;
    document.getElementById('bread').style.display='none';refresh();
  }
});
```

然后在 `refresh()` 函数定义之后、`refresh()` 调用之前，添加时间轴核心 JS：

```javascript
/* ══════════════════════════════════════════════════
   Interactive Timeline Component
   ══════════════════════════════════════════════════ */
var TL = {zoom:1,panX:0,isDragging:false,dragStartX:0,dragStartPan:0,blocks:[]};

function timeToSec(tstr){
  /* "2026-06-29 09:30:00" → seconds since midnight */
  var p=tstr.split(' ');
  if(p.length<2) return 0;
  var q=p[1].split(':');
  return parseInt(q[0])*3600+parseInt(q[1])*60+(parseInt(q[2])||0);
}

function buildTimelineBlocks(){
  /* Merge idle + normal timeline data into blocks */
  var items=DATA.timeline||[];
  var blocks=[];
  items.forEach(function(item){
    var startSec=timeToSec(item.started_at);
    if(startSec<0||startSec>=86400)return;
    var endSec=startSec+(item.duration||0);
    if(endSec>86400)endSec=86400;
    var l=(startSec/86400)*100;
    var w=((endSec-startSec)/86400)*100;
    var cc=item.color||CC[item.category]||'#888';
    blocks.push({
      left:l, width:Math.max(w,0.15),
      color:cc, cat:item.category,
      process:item.process, title:item.window_title||'',
      start:item.started_at, duration:item.duration||0,
      startSec:startSec, endSec:endSec
    });
  });
  blocks.sort(function(a,b){return a.startSec-b.startSec;});
  return blocks;
}

function renderTimelineChart(){
  var track=document.getElementById('tlTrack');
  if(!track)return;
  var ruler=document.getElementById('tlRuler');
  TL.blocks=buildTimelineBlocks();

  /* Render ruler marks */
  var rulerHTML='';
  var markInterval=3; /* hours between major marks; adjust by zoom */
  var z=TL.zoom;
  if(z>=8) markInterval=0.25;  /* 15 min */
  else if(z>=4) markInterval=1; /* 1h */
  else if(z>=2) markInterval=2; /* 2h */
  else markInterval=3;          /* 3h */

  rulerHTML+=rulerMark(0,'00:00','major');
  for(var h=markInterval; h<24; h+=markInterval){
    var min=(h%1)*60;
    var label=Math.floor(h).toString().padStart(2,'0')+':'+min.toString().padStart(2,'0');
    rulerHTML+=rulerMark((h/24)*100,label, h%3===0?'major':'minor');
  }
  rulerHTML+=rulerMark(100,'24:00','major');
  ruler.innerHTML=rulerHTML;

  /* Render blocks */
  var html='';
  TL.blocks.forEach(function(b){
    var sizeClass='';
    if(b.width<1.5) sizeClass=' tiny';
    else if(b.width<6) sizeClass=' small';
    var label=b.process+(b.title?' — '+b.title.slice(0,20):'');
    var sub=formatDuration(b.duration);
    html+='<div class="tl-block'+sizeClass+'" data-idx="'+TL.blocks.indexOf(b)+'" style="left:'+b.left+'%;width:'+b.width+'%;background:'+b.color+'">'
      +'<div class="bl">'+label+'</div>'
      +'<div class="bs">'+b.start.slice(11,16)+' — '+sub+'</div>'
      +'</div>';
  });
  track.innerHTML=html;

  /* Hover tooltip */
  track.querySelectorAll('.tl-block').forEach(function(el){
    el.addEventListener('mouseenter',function(e){
      var idx=parseInt(el.dataset.idx);
      var b=TL.blocks[idx]; if(!b)return;
      var ttip=document.getElementById('tlTooltip')||createTooltip();
      ttip.innerHTML='<div class="tt-cat" style="background:'+b.color+'22;color:'+b.color+'">'+b.cat+'</div>'
        +'<div class="tt-row"><span class="tt-label">程序</span><span>'+escHtml(b.process)+'</span></div>'
        +'<div class="tt-row"><span class="tt-label">窗口</span><span>'+escHtml(b.title.slice(0,40))+'</span></div>'
        +'<div class="tt-row"><span class="tt-label">时间</span><span>'+b.start.slice(11,16)+' — '+secToTimeStr(b.endSec)+'</span></div>'
        +'<div class="tt-row"><span class="tt-label">时长</span><span>'+formatDuration(b.duration)+'</span></div>';
      ttip.style.display='block';
      positionTooltip(e,ttip);
    });
    el.addEventListener('mousemove',function(e){
      var ttip=document.getElementById('tlTooltip');
      if(ttip) positionTooltip(e,ttip);
    });
    el.addEventListener('mouseleave',function(){
      var ttip=document.getElementById('tlTooltip');
      if(ttip) ttip.style.display='none';
    });
  });

  applyTimelineTransform();
  updateZoomLabel();
}

function rulerMark(pct,label,cls){
  return '<div class="rk '+cls+'" style="left:'+pct+'%">'+label+'</div>';
}

function formatDuration(s){
  var h=Math.floor(s/3600),m=Math.floor((s%3600)/60);
  return h?h+'h '+m+'m':m+'m';
}

function secToTimeStr(sec){
  var h=Math.floor(sec/3600),m=Math.floor((sec%3600)/60);
  return h.toString().padStart(2,'0')+':'+m.toString().padStart(2,'0');
}

var _tooltip=null;
function createTooltip(){
  _tooltip=document.createElement('div');
  _tooltip.id='tlTooltip';_tooltip.className='tl-tooltip';
  document.body.appendChild(_tooltip);
  return _tooltip;
}

function escHtml(s){return String(s).replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;').replace(/"/g,'&quot;');}

function positionTooltip(e,el){
  var x=e.clientX+16,y=e.clientY-10;
  var r=el.getBoundingClientRect();
  if(x+r.width>window.innerWidth) x=e.clientX-r.width-16;
  if(y<4) y=4;
  if(y+r.height>window.innerHeight) y=window.innerHeight-r.height-4;
  el.style.left=x+'px';el.style.top=y+'px';
}

function applyTimelineTransform(){
  var track=document.getElementById('tlTrack');
  var ruler=document.getElementById('tlRuler');
  var z=TL.zoom,px=TL.panX;
  var t='scaleX('+z+') translateX('+px+'px)';
  if(track) track.style.transform=t;
  if(ruler) ruler.style.transform=t;
  updateZoomLabel();
}

function updateZoomLabel(){
  var ranges={
    1:'24h 总览 (1×)',  2:'12h 范围 (2×)',  4:'6h 范围 (4×)',
    6:'4h 范围 (6×)',   8:'3h 范围 (8×)',  12:'1h 范围 (12×)',
    16:'45min (16×)'
  };
  var z=Math.round(TL.zoom);
  var label=ranges[z]||(z+'×');
  var el=document.getElementById('tlZoomLabel');
  if(el) el.textContent=label;
}

/* ── Zoom with wheel ── */
document.getElementById('tlBody')?.addEventListener('wheel',function(e){
  if(document.getElementById('timelineView').style.display==='none')return;
  e.preventDefault();
  var rect=this.getBoundingClientRect();
  var mouseX=e.clientX-rect.left;  /* mouse position relative to viewport */
  var oldZoom=TL.zoom;
  var factor=e.deltaY<0?1.25:0.8;
  var newZoom=Math.max(1,Math.min(16,oldZoom*factor));
  if(newZoom===oldZoom)return;
  /* Keep the point under the mouse stable */
  /* trackWidth at old zoom = 2400 * oldZoom, at current pan = panX */
  /* We want mouseX/oldZoom ratio to stay constant */
  var trackWidth=2400;
  var contentX=mouseX/TL.zoom;  /* position in 1× coordinate space */
  TL.panX=mouseX-(contentX*newZoom);
  TL.zoom=newZoom;
  document.getElementById('tlZoomSlider').value=newZoom;
  applyTimelineTransform();
},{passive:false});

/* ── Pan with drag ── */
var body=document.getElementById('tlBody');
body?.addEventListener('mousedown',function(e){
  if(document.getElementById('timelineView').style.display==='none')return;
  if(e.button!==0||e.target.closest('.tl-block'))return;  /* allow click on blocks */
  TL.isDragging=true;
  TL.dragStartX=e.clientX;
  TL.dragStartPan=TL.panX;
  body.style.cursor='grabbing';
});

document.addEventListener('mousemove',function(e){
  if(!TL.isDragging)return;
  var dx=e.clientX-TL.dragStartX;
  var maxPan=0;
  var minPan=-(2400*(TL.zoom-1)/TL.zoom*0.95);
  TL.panX=Math.max(minPan,Math.min(maxPan,TL.dragStartPan+dx));
  applyTimelineTransform();
});

document.addEventListener('mouseup',function(){
  if(TL.isDragging){
    TL.isDragging=false;
    if(body) body.style.cursor='grab';
  }
});

/* ── Zoom slider ── */
document.getElementById('tlZoomSlider')?.addEventListener('input',function(){
  var newZoom=parseFloat(this.value);
  /* Center the view when using slider */
  var viewportWidth=document.getElementById('tlBody').clientWidth;
  TL.panX=viewportWidth/2-(2400*newZoom/2);
  TL.zoom=newZoom;
  applyTimelineTransform();
});

/* ── Zoom buttons ── */
document.getElementById('tlZoomOut')?.addEventListener('click',function(){
  TL.zoom=Math.max(1,TL.zoom/1.25);
  document.getElementById('tlZoomSlider').value=TL.zoom;
  applyTimelineTransform();
});
document.getElementById('tlZoomIn')?.addEventListener('click',function(){
  TL.zoom=Math.min(16,TL.zoom*1.25);
  document.getElementById('tlZoomSlider').value=TL.zoom;
  applyTimelineTransform();
});

/* ── Initialize on page load ── */
refresh();
```

同时修改原来的 `refresh()` 调用（第 443 行的 `refresh();`），如果已经是 `refresh();` 则保持不变。

- [ ] **Step 5: 验证静态语法**

```bash
cd d:/repos/我的/tracker && ../venv/Scripts/python -c "
import stats_html
# Test that HTML_TEMPLATE still has all required placeholders
assert '__EMBEDDED_DATA__' in stats_html.HTML_TEMPLATE, 'Missing data placeholder'
assert 'timeline' in stats_html.HTML_TEMPLATE, 'Missing timeline tab'
assert 'tlTrack' in stats_html.HTML_TEMPLATE, 'Missing timeline component'
print('Template OK')
"
```

- [ ] **Step 6: 提交**

```bash
cd d:/repos/我的 && git add tracker/stats_html.py
git commit -m "feat: add interactive timeline with zoom/pan on stats page"
```

---

### Task 6: 集成验证

- [ ] **Step 1: 运行全部测试**

```bash
cd d:/repos/我的/tracker && ../venv/Scripts/python -m pytest tests/ -v
```
Expected: 全部 PASSED

- [ ] **Step 2: 手动验证（可选 — 启动程序）**

```bash
cd d:/repos/我的/tracker && ../venv/Scripts/python main.py
```
1. 验证程序启动正常
2. 点击系统托盘 → 打开统计 → 确认今日/本周/本月饼图出现"空闲"和"视频"分类
3. 点击「时间轴」tab → 确认时间轴显示当日活动色块
4. 在时间轴上滚轮缩放 → 确认缩放正常
5. 拖拽平移 → 确认平移正常
6. 悬停色块 → 确认 tooltip 出现

- [ ] **Step 3: 最终提交**

```bash
cd d:/repos/我的 && git add -A
git commit -m "feat: idle tracking and interactive timeline complete"
```
