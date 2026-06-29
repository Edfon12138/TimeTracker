# Windows 程序运行时间追踪器 — 设计文档

## 概述

一个 Windows 桌面应用，在后台静默记录所有前台程序的运行时间，支持窗口标题级别的精细追踪和自动分类，通过系统托盘提供轻盈的交互入口，统计面板可查看每日/每周/每月/自定义时间范围的详细报告。

**使用场景**：个人时间管理，了解每天花在各个应用上的时间分布。

**设计参考**：[stats-panel-mockup.html](../../stats-panel-mockup.html) — 统计面板视觉稿

---

## 技术栈

| 层 | 选型 | 理由 |
|---|------|------|
| 语言 | Python 3.12+ | 代码密度低，Claude 修改效率高，单文件改动即可测试 |
| UI 框架 | PySide6 | Qt 的 Python 绑定，系统托盘、图表嵌入、原生 Windows 外观 |
| Windows API | pywin32 + ctypes | 前台窗口监听、空闲检测、进程信息获取、图标提取 |
| 数据库 | SQLite（内置 sqlite3） | 零配置、单文件、查询能力强、与 Python 无缝集成 |
| 图表 | matplotlib (FigureCanvasQTAgg) | 嵌入 PySide6，中文支持好，饼图/柱状图均可 |
| 打包 | PyInstaller | 单 exe 分发，~50MB |

## 架构

### 模块划分（共 11 个文件）

```
┌─────────────────────────────────────────────────┐
│                  系统托盘 (tray.py)               │
│  托盘图标 + 右键菜单 → 统计面板 / 暂停 / 退出      │
└──────────────┬──────────────────────────────────┘
               │
┌──────────────┴──────────────┐      ┌────────────┐
│      窗口监控引擎 (monitor.py)│  ──▶  │  SQLite   │
│                              │      │  (storage) │
│  Win32 Hook → 前台窗口变化   │      └─────┬──────┘
│  → 提取进程名 + 窗口标题     │            │
│  → 记录上一窗口活跃时长       │  ┌─────────┴────────┐
│  → 5秒最小阈值过滤           │  │  storage.py      │
└──────────────┬──────────────┘  │  统计查询 + 聚合   │
               │                 └─────────┬────────┘
               │  ┌──────────────┐         │
               ├─▶│ idle_detector │         │
               │  │ 空闲检测      │         │
               │  └──────────────┘         │
               │  ┌──────────────┐         │
               └─▶│ classifier.py│◀────────┘
                  │ 自动分类器    │
                  └──────────────┘
```

| # | 模块 | 文件 | 职责 |
|---|------|------|------|
| 1 | `monitor.py` | 1 文件 | 前台窗口变化监听、进程名/窗口标题提取、时长累计 |
| 2 | `idle_detector.py` | 1 文件 | GetLastInputInfo 空闲检测，超时暂停记录 |
| 3 | `classifier.py` | 1 文件 | 规则引擎匹配 → 自动分类标签 |
| 4 | `storage.py` | 1 文件 | SQLite CRUD、聚合查询、数据清理 |
| 5 | `tray.py` | 1 文件 | 系统托盘图标、右键菜单、应用生命周期 |
| 6 | `stats_window.py` | 1 文件 | 统计面板主窗口（标签页、工具栏） |
| 7 | `charts.py` | 1 文件 | matplotlib 饼图/柱状图嵌入、悬停交互 |
| 8 | `classifier_edit.py` | 1 文件 | 分类规则编辑器（设置页内嵌） |
| 9 | `config.py` | 1 文件 | JSON 配置文件读写 |
| 10 | `icon_extractor.py` | 1 文件 | Win32 API 提取 exe 图标 |
| 11 | `main.py` | 1 文件 | 入口，启动托盘和监控引擎 |

### 核心数据流

```
前台窗口变化 (Win32 EVENT_SYSTEM_FOREGROUND)
  → monitor 捕获: 进程名 + 窗口标题
  → 如果距上次切换 < 5s: 丢弃（快速切换过滤）
  → idle_detector 检查是否空闲
  → classifier 匹配规则，打标签
  → storage 写入 activity_log 行 + 增量更新 daily_summary
  → tray 更新悬浮提示（今日用时）
```

---

## 核心算法

### 1. 窗口监控引擎

**方式**：`SetWinEventHook` 注册 `EVENT_SYSTEM_FOREGROUND` 事件钩子（事件驱动，非轮询）。

伪代码：

```
当前活跃 = { process, window_title, started_at, is_idle }

on_foreground_change(new_hwnd):
    now = time()
    如果当前活跃存在:
        duration = now - 当前活跃.started_at
        如果 duration >= 5秒:
            写入数据库(当前活跃)
    
    new_process = get_process_name(new_hwnd)
    new_title = get_window_text(new_hwnd)
    
    如果 new_process 不同于 当前活跃.process
       或 new_title 不同于 当前活跃.window_title:
        当前活跃 = { new_process, new_title, now, False }
```

**消息泵**：PySide6 的 Qt 事件循环承载 Win32 消息钩子，不需额外消息循环。

**特殊场景**：
- 快速切换（< 5 秒）：直接丢弃，不计入任何程序
- 锁屏/睡眠：监听 `WM_WTSSESSION_CHANGE`，锁屏时结算当前段并暂停
- 同一窗口标题变化（如浏览器切换标签页）：记录为新段

### 2. 空闲检测

**API**：`GetLastInputInfo()` — 返回距上一次键鼠输入的毫秒数。

```
检查间隔: 30 秒
空闲阈值: 5 分钟（可在设置中调整，范围 1-30 分钟）

每次检查:
    idle_ms = GetLastInputInfo()
    如果 idle_ms > 阈值 且 当前未标记空闲:
        结算当前活跃窗口（截止到 阈值前）
        标记 is_idle = True
    如果 idle_ms < 阈值 且 当前已标记空闲:
        以"用户回来时间"为起点，重启当前窗口计时
        标记 is_idle = False
```

### 3. 自动分类器

两级匹配，配置驱动：

```json
{
  "categories": {
    "工作": {"color": "#7BA78E"},
    "娱乐": {"color": "#D4956B"},
    "浏览": {"color": "#7B9EC7"},
    "通讯": {"color": "#A78BB5"},
    "系统": {"color": "#6B6B6B"},
    "其他": {"color": "#5A5A5A"}
  },
  "rules": [
    {"process": "Code.exe", "category": "工作"},
    {"process": "chrome.exe", "title_pattern": "GitHub|Jira|Stack Overflow", "category": "工作"},
    {"process": "chrome.exe", "title_pattern": "YouTube|Netflix|Bilibili", "category": "娱乐"},
    {"process": "WeChat.exe", "category": "通讯"}
  ],
  "defaults": {
    "chrome.exe": "浏览",
    "msedge.exe": "浏览"
  }
}
```

**匹配优先级**：有 title_pattern 的精确匹配 > 仅有 process 的匹配 > defaults > "其他"。

**自演进**：所有未被规则覆盖的 (进程, 标题片段) 汇入"待分类"列表，用户可在设置中一键归入某类别，规则自动追加。

### 4. 程序图标提取

```
SHGetFileInfo(exe_path, 0, SHGFI_ICON | SHGFI_SMALLICON)
  → HICON → QPixmap
```

- 缓存已提取图标，避免重复调用
- 系统进程（如 explorer.exe）使用预设图标
- UWP 应用通过包名查找图标

---

## 数据模型

### SQLite 表设计

```sql
-- 核心表：每条窗口活跃记录
CREATE TABLE activity_log (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    process      TEXT NOT NULL,
    window_title TEXT NOT NULL,
    category     TEXT DEFAULT '其他',
    started_at   DATETIME NOT NULL,
    duration     INTEGER NOT NULL,   -- 秒
    date         TEXT NOT NULL,       -- "2026-06-29" 冗余字段加速按日查询
    created_at   DATETIME DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_activity_date ON activity_log(date);
CREATE INDEX idx_activity_category ON activity_log(category, date);

-- 每日汇总缓存（统计面板秒开）
CREATE TABLE daily_summary (
    date         TEXT NOT NULL,
    category     TEXT NOT NULL,
    total_seconds INTEGER NOT NULL,
    PRIMARY KEY (date, category)
);

-- 分类规则（与配置文件双向同步）
CREATE TABLE classification_rules (
    id             INTEGER PRIMARY KEY AUTOINCREMENT,
    process        TEXT NOT NULL,
    title_pattern  TEXT,
    category       TEXT NOT NULL,
    is_user_added  INTEGER DEFAULT 0
);
```

### 写入策略

- `activity_log`：每次切换即时写入（5 秒阈值过滤后）
- `daily_summary`：同一事务内增量更新 `total_seconds`
- 避免攒批：防止崩溃丢数据

### 数据保留

- 默认保留 90 天 `activity_log` 原始记录，超期自动清理（应用启动时检查）
- `daily_summary` 永久保留（数据量极小）
- 保留天数在设置界面可选：30 / 60 / 90 / 180 / 永久

---

## UI 设计

详见 [stats-panel-mockup.html](../../stats-panel-mockup.html)。

### 设计语言：精密仪表盘

- **基调**：深色表面 `#1E2027`，深层底色 `#16181D`
- **强调色**：铜色/琥珀 `#D4956B`（选中态、主按钮、活跃标签）
- **分类色板**：工作绿 `#7BA78E`、娱乐铜 `#D4956B`、浏览蓝 `#7B9EC7`、通讯紫 `#A78BB5`
- **程序色**：每个程序使用其 exe 图标的主题色（通过图标提取获得），使图表中程序各具独立视觉标识
- **字体**：等宽数字 `Consolas` / `Cascadia Code`，UI 文字 `Segoe UI` / `Microsoft YaHei`

### 系统托盘

```
托盘图标: 时钟样式
  ├── 悬浮提示: "记录中 · 今日 5h 42m"
  └── 右键菜单:
        ├── 打开统计面板
        ├── ──────────
        ├── 暂停记录 / 恢复记录
        └── 退出
```

### 统计面板

- **时间范围标签**：今日 / 本周 / 本月 / 自定义（自定义展开日期选择器）
- **视图切换**：按分类 / 按程序
- **图表切换**：饼图 / 柱状图
- **联动悬停**：
  - 悬停饼图扇区 → 该扇区放大+发光，其余变暗；右侧列表同步高亮对应项；弹出分类名+时长+占比提示
  - 悬停右侧列表项 → 饼图/柱状图对应扇区/柱子高亮
- **分类下钻**：按分类视图点击某分类 → 展开该分类下所有程序明细，出现面包屑"← 返回全部"
- **按程序查看**：每个程序独立扇区/柱子，使用图标主题色，悬停时各自独立高亮互不影响
- **柱状图**：柱子垂直居中，程序图标+标签+比例条+时间标注，短条标注在条外不溢出
- **时间线**：在图表下方，按时间顺序列出今日活动记录，每条含程序图标+窗口标题+时长+分类标签
- **导出**：CSV / Excel 按钮

### 设置面板

| 设置项 | 默认值 | 说明 |
|--------|--------|------|
| 最小记录阈值 | 5 秒 | 低于此值的窗口切换不记录 |
| 空闲超时 | 5 分钟 | 超时暂停计时，范围 1-30 分钟 |
| 数据保留天数 | 90 天 | 选项：30/60/90/180/永久 |
| 开机自启 | 关闭 | 注册到 Windows 启动项 |
| 分类规则编辑 | — | 内嵌编辑器，增删改规则 |

---

## 配置文件

`config.json`，与 exe 同目录：

```json
{
  "min_duration_sec": 5,
  "idle_timeout_min": 5,
  "retention_days": 90,
  "autostart": false,
  "export_path": "",
  "categories": { ... },
  "rules": [ ... ],
  "defaults": { ... }
}
```

---

## 错误处理与边界情况

| 场景 | 处理方式 |
|------|----------|
| 监控引擎崩溃 | try-except 包裹回调，写入错误日志，自动重启监控 |
| 数据库锁 | WAL 模式，写入重试 3 次 |
| 数据库损坏 | 启动时执行 `PRAGMA integrity_check`，损坏则重建并备份旧文件 |
| 休眠/睡眠恢复 | 监听电源事件，睡眠期间不计时，唤醒后重新开始 |
| 用户快速 Alt+Tab | 5 秒阈值自动过滤 |
| 程序被卸载（exe 不存在） | 图标提取失败时使用默认图标 |
| 同时运行多个实例 | 启动时检测互斥锁，只允许单实例 |
| 系统关机 | 监听 `WM_QUERYENDSESSION`，结算当前段后正常退出 |

---

## 测试策略

| 层级 | 内容 | 工具 |
|------|------|------|
| 单元测试 | classifier 规则匹配逻辑、storage CRUD、config 读写 | pytest |
| 集成测试 | monitor → classifier → storage 完整链路 | pytest + 模拟窗口切换 |
| 手动验证 | 真实运行，切换窗口，查看统计面板数据准确性 | 肉眼核对 |

---

## 开发顺序

1. `config.py` + `storage.py` — 配置和数据层先行
2. `classifier.py` — 分类器及内置规则
3. `monitor.py` + `idle_detector.py` — 核心监控引擎（可独立测试）
4. `icon_extractor.py` — 图标提取
5. `tray.py` — 系统托盘，让程序"跑起来"
6. `stats_window.py` + `charts.py` — 统计面板
7. `classifier_edit.py` — 设置页/规则编辑器
8. `main.py` — 整合入口
9. 打包脚本 + 测试
