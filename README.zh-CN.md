# ⏱ Windows 时间追踪器 (TimeTracker)

> [English](README.md) | 中文

自动记录你在电脑上每个程序/窗口花费的时间，分类统计，交互式时间轴查看。

## 功能

- **自动追踪** — 后台运行，按窗口标题和进程名自动记录活跃时间
- **智能分类** — 内置 100+ 条规则，覆盖开发、办公、设计、浏览器、通讯、游戏、影音等
- **空闲检测** — 无操作时自动暂停，恢复后继续记录
- **视频识别** — 检测到播放器/视频网站时单独归类
- **交互式统计** — 饼图/柱状图、程序排名、分类汇总
- **时间线 + 时间轴** — 活动列表 + 可缩放/拖拽的 24h 交互式时间轴
- **系统托盘** — 最小化到托盘，右键菜单操作
- **便携模式** — 所有数据（配置、数据库、图标缓存）保存在 exe 同目录

## 快速开始

### 直接运行（Python）

```bash
pip install -r tracker/requirements.txt
python tracker/main.py
```

### 打包为 exe

```bash
pip install pyinstaller
pyinstaller --onefile --windowed --name TimeTracker tracker/main.py
```

运行 `dist/TimeTracker.exe` 即可。

## 使用说明

1. 启动后系统托盘出现时钟图标 🕐
2. 程序自动记录前台窗口的活动时间
3. 右键托盘图标 → **打开统计** → 浏览器中查看
4. 右键 → **暂停/继续** → 临时停止记录
5. 右键 → **设置** → 编辑 `config.json` 中的分类规则

### 统计页面

- **今日 / 本周 / 本月** — 切换统计周期
- **按分类 / 按程序** — 饼图/柱状图切换
- **分类下钻** — 点击分类查看具体程序详情
- **时间线** — 按时间顺序的活动列表
- **⚙ 设置** — 页面内直接编辑分类规则

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
└── tests/               # pytest 测试（17 个）
```

## 技术栈

| 组件 | 方案 |
|------|------|
| 运行时 | Python 3.13 |
| GUI | PySide6 (Qt) — 仅系统托盘 |
| 数据库 | SQLite (WAL 模式) |
| 图表 | Chart.js via 本地 HTTP 服务 |
| 图标提取 | Windows SHGetFileInfo API |
| 打包 | PyInstaller（单文件 exe） |

## 许可证

MIT
