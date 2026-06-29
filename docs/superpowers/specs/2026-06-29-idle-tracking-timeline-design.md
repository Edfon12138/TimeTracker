# 空闲追踪 + 交互时间轴 — 设计文档

## 概述

在现有 TimeTracker 基础上扩展两个功能：
1. **空闲/视频检测** — 将无操作时间和「在看视频」时间纳入时间统计
2. **交互时间轴** — 在统计页面新增一个可缩放、可拖拽的时间轴可视化组件

不修改数据库结构，空闲会话数据仅存内存，在生成 HTML 统计页面时合并展示。

---

## 一、空闲/视频检测

### 1.1 空闲会话数据结构

在 `idle_detector.py` 中新增内存缓存 `_idle_sessions: list[dict]`，每条记录：

```python
{
  "started_at": 1719622800.0,     # unix timestamp 空闲开始
  "ended_at":   1719626400.0,     # unix timestamp 空闲结束
  "process":    "chrome.exe",     # 空闲开始时的前台进程
  "window_title": "YouTube - ...", # 空闲开始时的窗口标题
  "is_video":   True,             # 是否检测为视频播放
  "category":   "视频"            # "视频" 或 "空闲"
}
```

### 1.2 检测流程

```
检测线程每 30 秒轮询 GetLastInputInfo()
         │
         ▼
  ┌─ 非空闲 → 空闲 ──────────────────────┐
  │   1. user32.GetForegroundWindow()    │
  │   2. 提取进程名 + 窗口标题           │
  │   3. 窗口标题匹配视频关键词：         │
  │      YouTube|Netflix|Bilibili|Twitch │
  │      |放映|播放|视频|直播|影视|追剧  │
  │      |Plex|DisneyPlus|HBO|Crunchyroll│
  │      匹配 → "视频"，否则 → "空闲"     │
  │   4. 创建 session 记录               │
  │   5. 回调 _on_idle(session)          │
  └──────────────────────────────────────┘
         │
  ┌─ 空闲 → 非空闲 ──────────────────────┐
  │   1. 补全 session.ended_at = now()   │
  │   2. 回调 _on_resume(session)        │
  └──────────────────────────────────────┘
```

### 1.3 视频关键词检测

在 `classifier.py` 新增 `match_video_keywords(title: str) -> bool` 函数，匹配逻辑与现有 classifier 规则引擎一致，关键词列表硬编码（同时可被 config.json 中的规则覆盖）。

关键词来源：
- 视频平台：`YouTube`, `Netflix`, `Bilibili`, `Twitch`, `DisneyPlus`, `HBO`, `Crunchyroll`
- 中文关键词：`放映`, `播放`, `视频`, `直播`, `影视`, `追剧`, `弹幕`, `正在播放`
- 播放器：`mpv`, `PotPlayer`, `VLC`, `完美解码`, `KMPlayer`

### 1.4 数据流向

```
idle_detector.py
  └─ _idle_sessions: list[dict]    ← 纯内存，不落库
       │
       └─ idle_detector.get_idle_sessions() → list[dict]
              │
              ▼
       stats_html.generate()
              │
              ├─ 合并到 dp["today"]["cat"] — 追加 "空闲"/"视频" 分类时长
              ├─ 合并到 dp["week"]["cat"]   — 同上
              ├─ 合并到 dp["month"]["cat"]  — 同上
              └─ 合并到 dp["timeline"]      — 插入为 timeline 事件
```

### 1.5 分类颜色

| 分类 | 颜色 | 用途 |
|------|------|------|
| `空闲` | `#6B7280` | 无操作时段，灰调 |
| `视频` | `#8B5CF6` | 在看视频，紫色，区别于现有 5 个分类 |

颜色在 HTML 模板的 `CC` map 中硬编码（与现有工作/娱乐等一致）。

---

## 二、交互时间轴组件

### 2.1 布局

在顶部 tab 栏中新增标签：
```
[ 今日 | 本周 | 本月 | 时间轴 ]      ⚙
```

点击「时间轴」tab 时，`content` 区域显示时间轴组件，隐藏今日/本周/本月的图表和列表。

### 2.2 视觉结构

```
┌─ #timeline-container ────────────────────────────────────────────┐
│                                                                    │
│  ┌─ #timeline-header ──── 时间标尺（固定，不随缩放变化） ────────┐ │
│  │  00:00  03:00  06:00  09:00  12:00  15:00  18:00  21:00  24:00│ │
│  └───────────────────────────────────────────────────────────────┘ │
│                                                                    │
│  ┌─ #timeline-body ────────── 视口 (overflow:hidden) ───────────┐ │
│  │                                                               │ │
│  │   ┌─ #timeline-track ── CSS transform: scaleX() translateX() ┐│ │
│  │   │                                                          ││ │
│  │   │  ████████████████░░░░░░░░█████████████████████░░░░░░░░   ││ │
│  │   │  VS Code 工作     │ 空闲 │ Chrome 浏览      │ 视频     ││ │
│  │   │  09:00-11:45      │11:45 │ 13:00-16:20      │16:20-17:05││ │
│  │   │                   │-12:50│                   │          ││ │
│  │   │                                                          ││ │
│  │   └──────────────────────────────────────────────────────────┘│ │
│  │                                                               │ │
│  └───────────────────────────────────────────────────────────────┘ │
│                                                                    │
│  ┌─ #timeline-footer ── 缩放级别指示 ───────────────────────────┐ │
│  │   ◀─────  24h 总览 (1×)  ──────▶  放大                        │ │
│  └───────────────────────────────────────────────────────────────┘ │
└───────────────────────────────────────────────────────────────────┘
```

### 2.3 交互行为

| 操作 | 效果 | 实现方式 |
|------|------|---------|
| **滚轮上滚** | 以鼠标位置为中心放大（zoom *= 1.25） | `wheel` 事件 + CSS scaleX |
| **滚轮下滚** | 缩小（zoom /= 1.25），最多缩到 1× | 同上 |
| **按住拖拽**（左键） | 平移时间轴 | `mousedown/mousemove/mouseup` 改变 translateX |
| **悬停色块** | 显示 tooltip：进程名、窗口标题、起止时间、时长、分类 | `mouseenter/mouseleave` + 动态 div |
| **色块点击** | 高亮此行，在右侧/下方显示详细信息面板 | `click` 事件切换 CSS class |

### 2.4 缩放级别

| zoom 值 | 显示范围 | 刻度间隔 | 用途 |
|---------|---------|---------|------|
| 1× (最小) | 24h | 3h | 全天概览 |
| 2× | 12h | 1h | 半日查看 |
| 4× | 6h | 30min | 专注区间 |
| 6× | 4h | 20min | 精细查看 |
| 8× | 3h | 15min | 更精细 |
| 12× | 1h | 5min | 极限细节 |
| 16× (最大) | 45min | 5min | 分钟级查看 |

### 2.5 活动块定位算法

```javascript
// 每个活动的 x 位置和宽度按时间比例计算
const dayStart = 0;   // 00:00 = 0
const dayEnd = 86400; // 24:00 = 86400 秒

function getBlockStyle(activity, zoom, pan) {
  const startSec = timeToSeconds(activity.started_at);
  const endSec = timeToSeconds(activity.ended_at) || startSec + activity.duration;
  const left = (startSec / 86400) * 100;   // 百分比
  const width = ((endSec - startSec) / 86400) * 100;
  return {
    left: left + '%',
    width: width + '%',
    backgroundColor: activity.color
  };
}
```

### 2.6 实现方案

纯 DOM + CSS transform，不依赖 Chart.js 或第三方库：

- `#timeline-track` 容器：`position: relative; transform: scaleX(zoom) translateX(panX); transform-origin: left center`
- 活动块：`position: absolute; left: X%; width: W%; height: 38px; border-radius: 4px; cursor: pointer`
- 活动块文字：进程名 + 时间 → 若宽度 < 8% 则只显示缩写
- 时间标尺：固定于视口顶部，根据当前 zoom 级别计算刻度值
- 尾部缩放指示器：显示当前范围和级别

### 2.7 缩放边界限制

```javascript
const MIN_ZOOM = 1;    // 最小 1×（24h 全览）
const MAX_ZOOM = 16;   // 最大 16×（约 45min）
const ZOOM_STEP = 1.25;

function clampZoom(z) {
  return Math.max(MIN_ZOOM, Math.min(MAX_ZOOM, z));
}
```

`panX` 限制：不允许平移后 track 两端露出空白区。
- panX 最小值：`-(trackWidth * (zoom - 1) / zoom)` → 向右拖到尽头
- panX 最大值：`0` → 回到起点

### 2.8 与现有页面的集成

```html
<div class="content">
  <!-- 今日/本周/本月的统计内容 -->
  <div id="statsView" class="main">...</div>
  <div id="timelineView" style="display:none"> <!-- 时间轴组件 --> </div>
</div>
```

tab 切换逻辑：

```javascript
// 在现有 tab 点击事件中增加 'timeline' 分支
document.getElementById('timeTabs').addEventListener('click', function(e) {
  const tab = e.target.closest('.tab');
  if (!tab || !tab.dataset.r) return;
  
  if (tab.dataset.r === 'timeline') {
    document.getElementById('statsView').style.display = 'none';
    document.getElementById('timelineView').style.display = 'block';
    renderTimeline();  // 初始化时间轴
  } else {
    document.getElementById('statsView').style.display = 'flex';
    document.getElementById('timelineView').style.display = 'none';
    // 原来的刷新逻辑
  }
});
```

---

## 三、涉及文件改动清单

| 文件 | 改动类型 | 具体变更 |
|------|---------|---------|
| `idle_detector.py` | 修改 | 新增 `_idle_sessions` 缓存、`get_idle_sessions()`, `clear_idle_sessions()` |
| `classifier.py` | 新增函数 | `match_video_keywords(title)` 检测窗口标题是否含视频关键词 |
| `monitor.py` | 新增函数 | `get_current_window()` 返回当前 (process, title) |
| `stats_html.py` | 修改 | `generate()` 中读取空闲会话、合并到数据、嵌入视频关键词列表 |
| `main.py` | 微小改动 | 如果 idle_detector 回调签名变化则调整 |
| `stats_html.py` 的模板 | 修改 | 新增 HTML `#timelineView` 区域、JS 时间轴组件、CSS 样式 |

**不改动的文件**：`config.py`, `config.json`, `storage.py`, `tray.py`, `icon_extractor.py`, `tests/`

---

## 四、边界情况

| 场景 | 处理方式 |
|------|----------|
| 空闲但无视频播放 | 记录为「空闲」，标记 `is_video: false` |
| 空闲 + 窗口是浏览器播放视频 | 窗口标题匹配关键词 → 记录为「视频」 |
| 空闲 + 窗口是全屏但非视频 | 标题无关键词 → 仍标记为「空闲」 |
| 空闲期间窗口标题变化 | 每轮轮询重新检查前台窗口；视频→空闲 或 空闲→视频 由标题决定 |
| 空闲很短（< 30秒） | idledetector 30s 轮询粒度，最短空闲约 30s |
| 程序启动时已有空闲会话 | 启动时 `clear_idle_sessions()` |
| 统计页面打开时新空闲开始/结束 | 关闭页面再打开或重新点击「打开统计」会获取最新数据 |
| 时间轴缩放溢出（zoom × pan 超出范围） | 限制 translateX，不允许滑出空白区域 |
