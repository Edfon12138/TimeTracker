# ⏱ Windows 时间追踪器 (TimeTracker)

自动记录你在电脑上每个程序/窗口花费的时间，分类统计，交互式时间轴查看。

## 功能

- **自动追踪** — 后台运行，按窗口标题和进程名自动记录活跃时间
- **智能分类** — 内置 97 条规则，覆盖开发、办公、设计、浏览器、通讯、游戏、影音等
- **空闲检测** — 无操作时自动暂停，恢复后继续记录
- **视频识别** — 检测到播放器/视频网站时单独归类
- **交互式统计** — 饼图/柱状图、程序排名、分类汇总
- **时间线 + 时间轴** — 活动列表 + 可缩放/拖拽的 24h 交互式时间轴
- **系统托盘** — 最小化到托盘，右键菜单操作
- **便携模式** — 所有数据（配置、数据库）保存在 exe 同目录

## 快速开始

### 直接运行（Python）

```bash
pip install -r tracker/requirements.txt
python tracker/main.py
```

### 打包为 exe（便携版）

```bash
pip install pyinstaller
pyinstaller --onefile --windowed --name TimeTracker tracker/main.py
```

运行 `dist/TimeTracker.exe` 即可。数据文件（`config.json`、`tracker.db`、`icons/`）自动创建在 exe 同目录。

## 使用说明

1. 启动程序后，系统托盘出现时钟图标 🕐
2. 程序自动记录前台窗口的活动时间
3. 右键托盘图标 → **打开统计** → 浏览器中查看
4. 右键 → **暂停/继续** → 临时停止记录
5. 右键 → **设置** → 编辑 `config.json` 中的分类规则

### 统计页面

- **今日 / 本周 / 本月** — 切换统计周期
- **按分类 / 按程序** — 饼图/柱状图切换
- **分类下钻** — 点击分类查看具体程序详情
- **时间线** — 按时间顺序的活动列表
- **时间轴** — 可缩放（滚轮）和拖拽（鼠标拖动）的交互式时间条

## 分类规则

规则存储在 `config.json` 的 `rules` 数组中，每条规则包含：

```json
{
  "process": "chrome.exe",
  "title_pattern": "GitHub|Jira|Stack Overflow",
  "category": "工作"
}
```

- `process` — 进程名（不区分大小写）
- `title_pattern` — 窗口标题正则（可选，不填则匹配该进程所有窗口）
- `category` — 分类名称（在 `categories` 中定义颜色）

规则按顺序匹配，**标题优先于进程**。浏览器等通用程序可以通过标题细分不同用途。

你也可以在统计页面的设置弹窗中直接编辑规则。

## 项目结构

```
tracker/
├── main.py              # 入口：托盘 + 定时器 + 调度
├── config.py            # config.json 读写 + 默认配置
├── storage.py           # SQLite 数据库 CRUD
├── monitor.py           # 前台窗口轮询
├── classifier.py        # 按规则分类
├── idle_detector.py     # 空闲/视频检测
├── icon_extractor.py    # 程序图标提取 + 磁盘缓存
├── stats_html.py        # HTML 统计页面生成 + HTTP 服务
├── tray.py              # 系统托盘（QSystemTrayIcon）
├── requirements.txt
└── tests/               # pytest 测试
```

## 技术栈

| 组件 | 方案 |
|------|------|
| GUI 框架 | PySide6 (Qt for Python) |
| 数据库 | SQLite |
| 统计图表 | Chart.js (嵌入式 HTTP 服务) |
| 图标提取 | Windows SHGetFileInfo API |
| 打包 | PyInstaller |

## 许可证

MIT
